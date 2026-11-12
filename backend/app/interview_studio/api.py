"""Interview Studio API.

Recruiter side (organization-scoped): reschedule, cancel, draft and approve
questions, read the report, record a decision.
Candidate side (own interviews only): confirm or decline, give consent, answer
one question at a time, resume after a disconnect, finish.

Rules enforced here, never in the browser:
- questions reach a candidate only after a recruiter approved them;
- a session needs the candidate's recorded consent for that interview;
- the decision is always entered by a human reviewer and changes nothing else.
"""
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.recruitment import application_for_org, audit, require_csrf
from app.interview_studio.models import InterviewAnswer, InterviewQuestion, InterviewReport
from app.interview_studio.questions import MAX_LENGTH, MAX_QUESTIONS, clean_questions, draft_questions
from app.models.schema import (
    Application, CandidateProfile, Interview, Job, JobRequirement, Notification, User, UserConsent,
)
from app.security.dependencies import get_current_user, get_db, require_recruiter_for_org

router = APIRouter(prefix="/api/interview-studio", tags=["Interview Studio"])
CONSENT_POLICY_VERSION = "interview-v1"
OPEN_STATES = {"scheduled", "in_progress"}
DECISIONS = {"advance", "hold", "reject"}
# Words too general to say anything about whether a requirement was discussed.
COMMON_WORDS = {"with", "have", "from", "that", "this", "year", "years", "experience", "good", "strong", "knowledge",
                "skills", "skill", "ability", "work", "working", "must", "should", "using", "basic", "least", "able"}


# ---------- helpers ----------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; treat them as UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def iso(value: datetime | None) -> str | None:
    value = aware(value)
    return value.isoformat() if value else None


def consent_purpose(interview_id: UUID) -> str:
    return f"interview_session:{interview_id}"


def has_consent(db: Session, user_id: UUID, interview_id: UUID) -> bool:
    latest = db.scalars(select(UserConsent).where(UserConsent.user_id == user_id,
                                                  UserConsent.purpose == consent_purpose(interview_id))
                        .order_by(UserConsent.recorded_at.desc(), UserConsent.id.desc())).first()
    return bool(latest and latest.granted)


def interview_for_org(db: Session, org_id: UUID, interview_id: UUID) -> tuple[Interview, Application, Job]:
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "Interview not found")
    application = application_for_org(db, org_id, interview.application_id)
    return interview, application, db.get(Job, application.job_id)


def interview_for_candidate(db: Session, user: User, interview_id: UUID) -> tuple[Interview, Job]:
    row = db.execute(select(Interview, Job)
                     .join(Application, Interview.application_id == Application.id)
                     .join(Job, Application.job_id == Job.id)
                     .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
                     .where(Interview.id == interview_id, CandidateProfile.user_id == user.id)).first()
    if not row:
        raise HTTPException(404, "Interview not found")
    return row[0], row[1]


def candidate_user_id(db: Session, application: Application) -> UUID | None:
    return db.scalar(select(CandidateProfile.user_id).where(CandidateProfile.id == application.candidate_id))


def notify(db: Session, user_id: UUID | None, kind: str, message: str) -> None:
    if user_id:
        db.add(Notification(user_id=user_id, kind=kind, message=message))


def question_rows(db: Session, interview_id: UUID) -> list[InterviewQuestion]:
    return list(db.scalars(select(InterviewQuestion).where(InterviewQuestion.interview_id == interview_id)
                           .order_by(InterviewQuestion.position)))


def answers_by_question(db: Session, interview_id: UUID) -> dict[UUID, InterviewAnswer]:
    rows = db.scalars(select(InterviewAnswer).where(InterviewAnswer.interview_id == interview_id))
    return {row.question_id: row for row in rows}


def interview_out(db: Session, interview: Interview, job: Job, *, consent: bool | None = None) -> dict:
    total = db.scalar(select(func.count(InterviewQuestion.id)).where(InterviewQuestion.interview_id == interview.id)) or 0
    answered = db.scalar(select(func.count(InterviewAnswer.id)).where(InterviewAnswer.interview_id == interview.id)) or 0
    data = {
        "id": str(interview.id), "application_id": str(interview.application_id), "job_title": job.title,
        "status": interview.status, "scheduled_at": iso(interview.scheduled_at), "timezone": interview.timezone,
        "duration_minutes": interview.duration_minutes, "meeting_url": interview.meeting_url,
        "candidate_response": interview.candidate_response, "candidate_note": interview.candidate_note,
        "questions_total": total, "questions_answered": answered,
        "session_started_at": iso(interview.session_started_at),
        "session_completed_at": iso(interview.session_completed_at),
    }
    if consent is not None:
        data["consent_given"] = consent
    return data


# ---------- request bodies ----------

class ScheduleInput(BaseModel):
    scheduled_at: datetime
    timezone: str = Field(min_length=1, max_length=64)
    duration_minutes: int = Field(default=30, ge=10, le=240)
    meeting_url: str | None = Field(default=None, max_length=500)

    @field_validator("scheduled_at")
    @classmethod
    def needs_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("scheduled_at must include a time zone offset, for example 2027-01-05T10:00:00+05:30")
        return value.astimezone(timezone.utc)

    @field_validator("timezone")
    @classmethod
    def known_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except Exception as exc:  # unknown key, bad format, or missing tz database
            raise ValueError("Unknown time zone. Use a name such as Asia/Kolkata") from exc
        return value

    @field_validator("meeting_url")
    @classmethod
    def web_link_only(cls, value: str | None) -> str | None:
        value = (value or "").strip() or None
        if value and not re.match(r"^https?://[^\s]+$", value, re.I):
            raise ValueError("Meeting link must start with http:// or https://")
        return value


class DraftInput(BaseModel):
    count: int = Field(default=6, ge=3, le=MAX_QUESTIONS)


class QuestionsInput(BaseModel):
    questions: list[str] = Field(min_length=1, max_length=MAX_QUESTIONS)


class DecisionInput(BaseModel):
    decision: str
    note: str = Field(min_length=4, max_length=4000)


class RespondInput(BaseModel):
    response: str
    note: str | None = Field(default=None, max_length=1000)


class ConsentInput(BaseModel):
    granted: bool


class AnswerInput(BaseModel):
    question_id: UUID
    answer: str = Field(min_length=1, max_length=6000)


# ---------- recruiter side ----------

@router.get("/organizations/{organization_id}/interviews/{interview_id}")
def recruiter_interview(organization_id: UUID, interview_id: UUID, _: User = Depends(require_recruiter_for_org),
                        db: Session = Depends(get_db)):
    interview, _application, job = interview_for_org(db, organization_id, interview_id)
    return interview_out(db, interview, job)


@router.patch("/organizations/{organization_id}/interviews/{interview_id}/schedule")
def reschedule(organization_id: UUID, interview_id: UUID, body: ScheduleInput, _: None = Depends(require_csrf),
               user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    interview, application, job = interview_for_org(db, organization_id, interview_id)
    if interview.status != "scheduled":
        raise HTTPException(409, "Only an interview that has not started can be rescheduled")
    if body.scheduled_at <= now_utc():
        raise HTTPException(422, "The interview time must be in the future")
    interview.scheduled_at = body.scheduled_at
    interview.timezone = body.timezone
    interview.duration_minutes = body.duration_minutes
    interview.meeting_url = body.meeting_url
    # A new time needs a new confirmation and a new reminder.
    interview.candidate_response = "pending"
    interview.candidate_note = None
    interview.reminder_sent_at = None
    notify(db, candidate_user_id(db, application), "interview_rescheduled",
           f"Your interview for {job.title} has a new time. Please confirm or decline it in your portal.")
    audit(db, organization_id, user.id, "interview.reschedule", "interview", interview.id)
    db.commit()
    return interview_out(db, interview, job)


@router.post("/organizations/{organization_id}/interviews/{interview_id}/cancel")
def cancel(organization_id: UUID, interview_id: UUID, _: None = Depends(require_csrf),
           user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    interview, application, job = interview_for_org(db, organization_id, interview_id)
    if interview.status not in OPEN_STATES:
        raise HTTPException(409, "This interview is already closed")
    interview.status = "cancelled"
    notify(db, candidate_user_id(db, application), "interview_cancelled",
           f"Your interview for {job.title} has been cancelled.")
    audit(db, organization_id, user.id, "interview.cancel", "interview", interview.id)
    db.commit()
    return interview_out(db, interview, job)


@router.post("/organizations/{organization_id}/interviews/{interview_id}/questions/draft")
def draft(organization_id: UUID, interview_id: UUID, body: DraftInput, _: None = Depends(require_csrf),
          __: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    """Suggest questions. Nothing is saved; the recruiter edits and approves them separately."""
    _interview, _application, job = interview_for_org(db, organization_id, interview_id)
    requirements = [label for label in db.scalars(select(JobRequirement.label).where(JobRequirement.job_id == job.id))]
    result = draft_questions(job.title, job.description, requirements, body.count)
    return {**result, "saved": False, "notice": "Drafts only. Edit them, then approve to save."}


@router.get("/organizations/{organization_id}/interviews/{interview_id}/questions")
def approved_questions(organization_id: UUID, interview_id: UUID, _: User = Depends(require_recruiter_for_org),
                       db: Session = Depends(get_db)):
    interview_for_org(db, organization_id, interview_id)
    return [{"id": str(q.id), "position": q.position, "text": q.text} for q in question_rows(db, interview_id)]


@router.put("/organizations/{organization_id}/interviews/{interview_id}/questions")
def approve_questions(organization_id: UUID, interview_id: UUID, body: QuestionsInput, _: None = Depends(require_csrf),
                      user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    """Recruiter approval: this is the only way questions are saved."""
    interview, _application, _job = interview_for_org(db, organization_id, interview_id)
    if interview.status != "scheduled" or interview.session_started_at is not None:
        raise HTTPException(409, "Questions cannot be changed once the candidate has started")
    for text in body.questions:
        if len(text.strip()) > MAX_LENGTH:
            raise HTTPException(422, f"Each question must be at most {MAX_LENGTH} characters")
    cleaned = clean_questions(body.questions)
    if len(cleaned) != len([q for q in body.questions if q.strip()]):
        raise HTTPException(422, "Some questions are too short, repeated, or ask about a personal topic that "
                                 "must not be asked in an interview. Edit them and approve again.")
    db.execute(delete(InterviewQuestion).where(InterviewQuestion.interview_id == interview_id))
    db.flush()
    for position, text in enumerate(cleaned, start=1):
        db.add(InterviewQuestion(interview_id=interview_id, position=position, text=text, approved_by_id=user.id))
    audit(db, organization_id, user.id, "interview.questions_approved", "interview", interview.id)
    db.commit()
    return [{"id": str(q.id), "position": q.position, "text": q.text} for q in question_rows(db, interview_id)]


@router.get("/organizations/{organization_id}/interviews/{interview_id}/report")
def report(organization_id: UUID, interview_id: UUID, _: User = Depends(require_recruiter_for_org),
           db: Session = Depends(get_db)):
    """Everything the reviewer needs in one place. It contains no score and no recommendation."""
    interview, _application, job = interview_for_org(db, organization_id, interview_id)
    answers = answers_by_question(db, interview_id)
    items = []
    for question in question_rows(db, interview_id):
        answer = answers.get(question.id)
        text = answer.answer if answer else None
        items.append({"position": question.position, "question": question.text, "answer": text,
                      "word_count": len(text.split()) if text else 0, "answered_at": iso(answer.updated_at) if answer else None})
    combined = " ".join(item["answer"] or "" for item in items).lower()
    coverage = []
    for label in db.scalars(select(JobRequirement.label).where(JobRequirement.job_id == job.id)):
        keywords = {word for word in re.findall(r"[a-z0-9+#.]{4,}", label.lower())} - COMMON_WORDS
        mentioned = sorted(word for word in keywords if word in combined)
        coverage.append({"requirement": label, "mentioned_in_answers": bool(mentioned), "matched_words": mentioned})
    started, finished = aware(interview.session_started_at), aware(interview.session_completed_at)
    decision = db.scalars(select(InterviewReport).where(InterviewReport.interview_id == interview_id)).first()
    return {
        "interview": interview_out(db, interview, job),
        "items": items,
        "requirement_mentions": coverage,
        "minutes_taken": round((finished - started).total_seconds() / 60, 1) if started and finished else None,
        "decision": ({"decision": decision.decision, "note": decision.decision_note,
                      "reviewer_id": str(decision.reviewer_id) if decision.reviewer_id else None,
                      "decided_at": iso(decision.decided_at)} if decision else None),
        "notice": "Word matches only show that a topic was mentioned. They are not an assessment; "
                  "a human reviewer reads the answers and decides.",
    }


@router.post("/organizations/{organization_id}/interviews/{interview_id}/decision")
def decide(organization_id: UUID, interview_id: UUID, body: DecisionInput, _: None = Depends(require_csrf),
           user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    interview, _application, _job = interview_for_org(db, organization_id, interview_id)
    if body.decision not in DECISIONS:
        raise HTTPException(422, "Decision must be advance, hold or reject")
    if interview.status != "completed":
        raise HTTPException(409, "A decision can be recorded only after the interview is completed")
    record = db.scalars(select(InterviewReport).where(InterviewReport.interview_id == interview_id)).first()
    if record:
        record.decision, record.decision_note, record.reviewer_id, record.decided_at = \
            body.decision, body.note.strip(), user.id, now_utc()
    else:
        db.add(InterviewReport(interview_id=interview_id, decision=body.decision, decision_note=body.note.strip(),
                               reviewer_id=user.id))
    audit(db, organization_id, user.id, f"interview.decision.{body.decision}", "interview", interview.id)
    db.commit()
    return {"interview_id": str(interview_id), "decision": body.decision}


# ---------- candidate side ----------

@router.get("/me/interviews")
def my_interviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Interview, Job)
                      .join(Application, Interview.application_id == Application.id)
                      .join(Job, Application.job_id == Job.id)
                      .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
                      .where(CandidateProfile.user_id == user.id)
                      .order_by(Interview.scheduled_at.desc())).all()
    return [interview_out(db, interview, job, consent=has_consent(db, user.id, interview.id)) for interview, job in rows]


@router.post("/me/interviews/{interview_id}/respond")
def respond(interview_id: UUID, body: RespondInput, _: None = Depends(require_csrf),
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    interview, job = interview_for_candidate(db, user, interview_id)
    if body.response not in {"confirmed", "declined"}:
        raise HTTPException(422, "Response must be confirmed or declined")
    if interview.status != "scheduled":
        raise HTTPException(409, "This interview can no longer be confirmed or declined")
    interview.candidate_response = body.response
    interview.candidate_note = (body.note or "").strip() or None
    notify(db, interview.interviewer_id, f"interview_{body.response}",
           f"{user.full_name} has {body.response} the interview for {job.title}.")
    audit(db, job.organization_id, user.id, f"interview.candidate_{body.response}", "interview", interview.id)
    db.commit()
    return interview_out(db, interview, job, consent=has_consent(db, user.id, interview.id))


@router.post("/me/interviews/{interview_id}/consent")
def record_consent(interview_id: UUID, body: ConsentInput, _: None = Depends(require_csrf),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    interview, job = interview_for_candidate(db, user, interview_id)
    db.add(UserConsent(user_id=user.id, purpose=consent_purpose(interview_id),
                       policy_version=CONSENT_POLICY_VERSION, granted=body.granted))
    audit(db, job.organization_id, user.id, "interview.consent_granted" if body.granted else "interview.consent_withdrawn",
          "interview", interview.id)
    db.commit()
    return {"interview_id": str(interview_id), "consent_given": body.granted, "policy_version": CONSENT_POLICY_VERSION}


def open_session(db: Session, user: User, interview_id: UUID) -> tuple[Interview, Job, list[InterviewQuestion]]:
    """All the gates a candidate must pass before seeing or answering a question."""
    interview, job = interview_for_candidate(db, user, interview_id)
    if interview.status not in OPEN_STATES:
        raise HTTPException(409, "This interview is not open")
    if interview.candidate_response == "declined":
        raise HTTPException(409, "You declined this interview")
    if not has_consent(db, user.id, interview_id):
        raise HTTPException(403, "Consent is required before the interview can start")
    questions = question_rows(db, interview_id)
    if not questions:
        raise HTTPException(409, "The questions for this interview are not ready yet")
    return interview, job, questions


def session_state(db: Session, interview: Interview, questions: list[InterviewQuestion]) -> dict:
    answers = answers_by_question(db, interview.id)
    pending = next((q for q in questions if q.id not in answers), None)
    return {
        "interview_id": str(interview.id), "status": interview.status,
        "total": len(questions), "answered": len(answers),
        "current": ({"id": str(pending.id), "position": pending.position, "text": pending.text} if pending else None),
        "all_answered": pending is None,
    }


@router.get("/me/interviews/{interview_id}/session")
def session(interview_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The next unanswered question only. Calling it again after a disconnect resumes at the same place."""
    interview, _job, questions = open_session(db, user, interview_id)
    return session_state(db, interview, questions)


@router.post("/me/interviews/{interview_id}/session/answers")
def save_answer(interview_id: UUID, body: AnswerInput, _: None = Depends(require_csrf),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    interview, job, questions = open_session(db, user, interview_id)
    answers = answers_by_question(db, interview_id)
    pending = next((q for q in questions if q.id not in answers), None)
    if pending is None:
        raise HTTPException(409, "All questions are already answered")
    if body.question_id != pending.id:
        raise HTTPException(409, "Answer the current question first")
    text = body.answer.strip()
    if not text:
        raise HTTPException(422, "The answer cannot be empty")
    db.add(InterviewAnswer(question_id=pending.id, interview_id=interview_id, answer=text))
    if interview.status == "scheduled":
        interview.status = "in_progress"
        interview.session_started_at = now_utc()
        audit(db, job.organization_id, user.id, "interview.session_started", "interview", interview.id)
    db.commit()
    return session_state(db, interview, questions)


@router.post("/me/interviews/{interview_id}/session/complete")
def complete(interview_id: UUID, _: None = Depends(require_csrf),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    interview, job, questions = open_session(db, user, interview_id)
    state = session_state(db, interview, questions)
    if not state["all_answered"]:
        raise HTTPException(409, "Answer every question before finishing")
    interview.status = "completed"
    interview.session_completed_at = now_utc()
    notify(db, interview.interviewer_id, "interview_completed",
           f"{user.full_name} has completed the interview for {job.title}. The answers are ready for review.")
    audit(db, job.organization_id, user.id, "interview.session_completed", "interview", interview.id)
    db.commit()
    return {**state, "status": "completed"}
