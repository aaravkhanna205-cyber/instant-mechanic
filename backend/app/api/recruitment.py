"""Phase 3 recruitment APIs. Organization-scoped reads/writes, CSRF-protected mutations.

No user-supplied organization or actor IDs are trusted for authorization.
"""
from datetime import datetime
from uuid import UUID
import hmac
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.schema import (
    Organization, OrganizationMembership, JobCategory, Job, User,
    CandidateProfile, Application, ApplicationStageHistory, Interview,
    InterviewFeedback, AuditLog,
)
from app.security.dependencies import get_db, get_current_user, get_session_record, require_recruiter_for_org
from app.security.sessions import SessionRecord
from app.core.config import settings

router = APIRouter(prefix="/api/recruitment", tags=["Recruitment"])
STAGES = {"applied", "screening", "shortlisted", "trade_test", "interview", "offer", "hired", "rejected", "withdrawn"}
JOB_STATES = {"draft", "published", "paused", "closed"}
INTERVIEW_STATES = {"scheduled", "in_progress", "completed", "cancelled", "no_show"}


def require_csrf(request: Request, record: SessionRecord = Depends(get_session_record)) -> None:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in settings.allowed_origins:
        raise HTTPException(403, "Origin not allowed")
    if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), record.csrf):
        raise HTTPException(403, "Invalid CSRF token")


def must_org(db: Session, org_id: UUID) -> Organization:
    org = db.get(Organization, org_id)
    if not org or not org.active:
        raise HTTPException(404, "Organization not found")
    return org


def job_for_org(db: Session, org_id: UUID, job_id: UUID) -> Job:
    job = db.get(Job, job_id)
    if not job or job.organization_id != org_id:
        raise HTTPException(404, "Job not found")
    return job


def application_for_org(db: Session, org_id: UUID, application_id: UUID) -> Application:
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")
    job_for_org(db, org_id, application.job_id)
    return application


def audit(db: Session, org_id: UUID, user_id: UUID, action: str, kind: str, target_id: UUID):
    db.add(AuditLog(organization_id=org_id, actor_id=user_id, action=action,
                    target_type=kind, target_id=str(target_id), context={}))


def job_out(job: Job):
    return {"id": str(job.id), "organization_id": str(job.organization_id), "title": job.title,
            "category_slug": job.category_slug, "description": job.description,
            "location": job.location, "employment_type": job.employment_type,
            "status": job.status, "created_at": job.created_at.isoformat() if job.created_at else None}


def application_out(a: Application, **extra):
    return {"id": str(a.id), "job_id": str(a.job_id), "candidate_id": str(a.candidate_id),
            "stage": a.stage, "applied_at": a.applied_at.isoformat() if a.applied_at else None, **extra}


def iso(value: datetime | None):
    return value.isoformat() if value else None


class OrganizationInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=120)


class JobInput(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    category_slug: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=12000)
    location: str | None = Field(default=None, max_length=150)
    employment_type: str = Field(default="full_time", max_length=40)
    status: str = "draft"


class JobPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=12000)
    location: str | None = Field(default=None, max_length=150)
    status: str | None = None


class CandidateInput(BaseModel):
    phone: str | None = Field(default=None, max_length=40)
    city: str | None = Field(default=None, max_length=120)
    skills: dict = Field(default_factory=dict)


class StageInput(BaseModel):
    stage: str
    note: str | None = Field(default=None, max_length=2000)


class InterviewInput(BaseModel):
    application_id: UUID
    scheduled_at: datetime
    interviewer_id: UUID | None = None
    meeting_url: str | None = Field(default=None, max_length=500)


    @field_validator("meeting_url")
    @classmethod
    def web_link_only(cls, value: str | None) -> str | None:
        # The link is shown to candidates as a clickable address, so only web links are accepted.
        value = (value or "").strip() or None
        if value and not re.match(r"^https?://[^\s]+$", value, re.I):
            raise ValueError("Meeting link must start with http:// or https://")
        return value


class InterviewPatch(BaseModel):
    status: str


class FeedbackInput(BaseModel):
    score: int = Field(ge=1, le=5)
    comments: str | None = Field(default=None, max_length=4000)


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    return [{"slug": c.slug, "title": c.title, "department": c.department}
            for c in db.scalars(select(JobCategory).order_by(JobCategory.title)).all()]


@router.get("/organizations")
def organizations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    statement = select(Organization).where(Organization.active.is_(True))
    if not user.is_platform_admin:
        statement = statement.join(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
    orgs = db.scalars(statement.order_by(Organization.name)).all()
    return [{"id": str(o.id), "name": o.name, "slug": o.slug} for o in orgs]


@router.post("/organizations", status_code=201)
def create_organization(body: OrganizationInput, _: None = Depends(require_csrf),
                        db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.is_platform_admin:
        raise HTTPException(403, "Platform admin required")
    org = Organization(name=body.name.strip(), slug=body.slug)
    db.add(org)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Organization slug already exists")
    audit(db, org.id, user.id, "organization.create", "organization", org.id)
    db.commit()
    return {"id": str(org.id), "name": org.name, "slug": org.slug}


@router.get("/public/jobs")
def public_jobs(db: Session = Depends(get_db), limit: int = 30):
    limit = max(1, min(limit, 100))
    jobs = db.scalars(select(Job).join(Organization).where(Job.status == "published", Organization.active.is_(True))
                      .order_by(Job.created_at.desc()).limit(limit)).all()
    return [job_out(j) for j in jobs]


@router.get("/organizations/{organization_id}/jobs")
def list_jobs(organization_id: UUID, _: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    must_org(db, organization_id)
    return [job_out(j) for j in db.scalars(select(Job).where(Job.organization_id == organization_id)
                                         .order_by(Job.created_at.desc())).all()]


@router.post("/organizations/{organization_id}/jobs", status_code=201)
def create_job(organization_id: UUID, body: JobInput, _: None = Depends(require_csrf),
               user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    must_org(db, organization_id)
    if body.status not in JOB_STATES:
        raise HTTPException(422, "Invalid job status")
    if not db.get(JobCategory, body.category_slug):
        raise HTTPException(422, "Unknown job category; seed official roles first")
    job = Job(organization_id=organization_id, created_by_id=user.id, **body.model_dump())
    db.add(job); db.flush()
    audit(db, organization_id, user.id, "job.create", "job", job.id)
    db.commit(); db.refresh(job)
    return job_out(job)


@router.get("/organizations/{organization_id}/jobs/{job_id}")
def get_job(organization_id: UUID, job_id: UUID, _: User = Depends(require_recruiter_for_org),
            db: Session = Depends(get_db)):
    return job_out(job_for_org(db, organization_id, job_id))


@router.patch("/organizations/{organization_id}/jobs/{job_id}")
def patch_job(organization_id: UUID, job_id: UUID, body: JobPatch, _: None = Depends(require_csrf),
              user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    job = job_for_org(db, organization_id, job_id)
    changes = body.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] not in JOB_STATES:
        raise HTTPException(422, "Invalid job status")
    for key, value in changes.items():
        if key != "location" and value is None:
            raise HTTPException(422, f"{key} cannot be null")
        setattr(job, key, value)
    audit(db, organization_id, user.id, "job.update", "job", job.id)
    db.commit(); db.refresh(job)
    return job_out(job)


@router.get("/me/candidate-profile")
def my_candidate_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        return {"exists": False, "phone": None, "city": None, "skills": {}}
    return {"exists": True, "phone": profile.phone, "city": profile.city, "skills": profile.skills or {}}


@router.put("/me/candidate-profile")
def upsert_candidate(body: CandidateInput, _: None = Depends(require_csrf),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
    profile.phone, profile.city, profile.skills = body.phone, body.city, body.skills
    db.commit(); db.refresh(profile)
    return {"id": str(profile.id), "city": profile.city, "skills": profile.skills}


@router.post("/jobs/{job_id}/apply", status_code=201)
def apply(job_id: UUID, _: None = Depends(require_csrf), user: User = Depends(get_current_user),
          db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.status != "published" or not must_org(db, job.organization_id):
        raise HTTPException(404, "Published job not found")
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        profile = CandidateProfile(user_id=user.id, skills={})
        db.add(profile); db.flush()
    if db.scalar(select(Application.id).where(Application.job_id == job_id, Application.candidate_id == profile.id)):
        raise HTTPException(409, "Already applied")
    application = Application(job_id=job_id, candidate_id=profile.id)
    db.add(application); db.flush()
    db.add(ApplicationStageHistory(application_id=application.id, changed_by_id=user.id, new_stage="applied"))
    audit(db, job.organization_id, user.id, "application.create", "application", application.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Already applied")
    db.refresh(application)
    return application_out(application)


@router.get("/me/applications")
def my_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = db.execute(select(Application, Job.title, Job.location)
                         .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
                         .join(Job, Application.job_id == Job.id)
                         .where(CandidateProfile.user_id == user.id)
                         .order_by(Application.applied_at.desc())).all()
    return [application_out(a, job_title=title, job_location=location) for a, title, location in records]


@router.get("/me/interviews")
def my_interviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Interview, Job.title)
                      .join(Application, Interview.application_id == Application.id)
                      .join(Job, Application.job_id == Job.id)
                      .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
                      .where(CandidateProfile.user_id == user.id)
                      .order_by(Interview.scheduled_at.desc())).all()
    return [{"id": str(i.id), "application_id": str(i.application_id), "job_title": title, "status": i.status,
             "scheduled_at": iso(i.scheduled_at), "meeting_url": i.meeting_url} for i, title in rows]


@router.get("/organizations/{organization_id}/applications")
def list_applications(organization_id: UUID, _: User = Depends(require_recruiter_for_org),
                      db: Session = Depends(get_db)):
    must_org(db, organization_id)
    rows = db.execute(select(Application, Job.title, User.full_name, User.email)
                      .join(Job, Application.job_id == Job.id)
                      .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
                      .join(User, CandidateProfile.user_id == User.id)
                      .where(Job.organization_id == organization_id)
                      .order_by(Application.applied_at.desc())).all()
    return [application_out(a, job_title=title, candidate_name=name, candidate_email=email)
            for a, title, name, email in rows]


@router.get("/organizations/{organization_id}/applications/{application_id}/history")
def application_history(organization_id: UUID, application_id: UUID, _: User = Depends(require_recruiter_for_org),
                        db: Session = Depends(get_db)):
    application_for_org(db, organization_id, application_id)
    rows = db.execute(select(ApplicationStageHistory, User.full_name)
                      .outerjoin(User, ApplicationStageHistory.changed_by_id == User.id)
                      .where(ApplicationStageHistory.application_id == application_id)
                      .order_by(ApplicationStageHistory.changed_at.desc())).all()
    return [{"id": str(h.id), "previous_stage": h.previous_stage, "new_stage": h.new_stage, "note": h.note,
             "changed_by": name, "changed_at": iso(h.changed_at)} for h, name in rows]


@router.get("/organizations/{organization_id}/candidates")
def candidates(organization_id: UUID, _: User = Depends(require_recruiter_for_org),
               db: Session = Depends(get_db)):
    must_org(db, organization_id)
    candidate_ids = select(Application.candidate_id).join(Job).where(Job.organization_id == organization_id).distinct()
    rows = db.execute(select(CandidateProfile, User).join(User, CandidateProfile.user_id == User.id)
                      .where(CandidateProfile.id.in_(candidate_ids))).all()
    return [{"id": str(p.id), "full_name": u.full_name, "email": u.email, "phone": p.phone,
             "city": p.city, "skills": p.skills} for p, u in rows]


@router.patch("/organizations/{organization_id}/applications/{application_id}/stage")
def change_stage(organization_id: UUID, application_id: UUID, body: StageInput,
                 _: None = Depends(require_csrf), user: User = Depends(require_recruiter_for_org),
                 db: Session = Depends(get_db)):
    if body.stage not in STAGES:
        raise HTTPException(422, "Invalid hiring stage")
    application = application_for_org(db, organization_id, application_id)
    previous = application.stage
    if previous == body.stage:
        return application_out(application)
    application.stage = body.stage
    db.add(ApplicationStageHistory(application_id=application.id, changed_by_id=user.id,
                                   previous_stage=previous, new_stage=body.stage, note=body.note))
    audit(db, organization_id, user.id, "application.stage_change", "application", application.id)
    db.commit(); db.refresh(application)
    return application_out(application)


@router.get("/organizations/{organization_id}/interviews")
def interviews(organization_id: UUID, _: User = Depends(require_recruiter_for_org),
               db: Session = Depends(get_db)):
    must_org(db, organization_id)
    rows = db.execute(select(Interview, Job.title, User.full_name)
                      .join(Application, Interview.application_id == Application.id)
                      .join(Job, Application.job_id == Job.id)
                      .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
                      .join(User, CandidateProfile.user_id == User.id)
                      .where(Job.organization_id == organization_id)
                      .order_by(Interview.scheduled_at.desc())).all()
    feedback = dict(db.execute(select(InterviewFeedback.interview_id, func.count(InterviewFeedback.id))
                               .where(InterviewFeedback.interview_id.in_([i.id for i, _, _ in rows]))
                               .group_by(InterviewFeedback.interview_id)).all()) if rows else {}
    return [{"id": str(i.id), "application_id": str(i.application_id), "status": i.status,
             "scheduled_at": iso(i.scheduled_at), "meeting_url": i.meeting_url,
             "job_title": title, "candidate_name": name, "feedback_count": feedback.get(i.id, 0)}
            for i, title, name in rows]


@router.post("/organizations/{organization_id}/interviews", status_code=201)
def schedule_interview(organization_id: UUID, body: InterviewInput, _: None = Depends(require_csrf),
                       user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    application_for_org(db, organization_id, body.application_id)
    if body.interviewer_id and not db.scalar(select(OrganizationMembership.id).where(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == body.interviewer_id,
        OrganizationMembership.role.in_(["owner", "admin", "recruiter", "interviewer"]))):
        raise HTTPException(422, "Interviewer must be a member of this organization")
    interview = Interview(**body.model_dump())
    db.add(interview); db.flush()
    audit(db, organization_id, user.id, "interview.schedule", "interview", interview.id)
    db.commit()
    return {"id": str(interview.id), "application_id": str(interview.application_id), "status": interview.status}


@router.patch("/organizations/{organization_id}/interviews/{interview_id}")
def update_interview(organization_id: UUID, interview_id: UUID, body: InterviewPatch,
                     _: None = Depends(require_csrf), user: User = Depends(require_recruiter_for_org),
                     db: Session = Depends(get_db)):
    if body.status not in INTERVIEW_STATES:
        raise HTTPException(422, "Invalid interview status")
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "Interview not found")
    application_for_org(db, organization_id, interview.application_id)
    interview.status = body.status
    audit(db, organization_id, user.id, "interview.update", "interview", interview.id)
    db.commit()
    return {"id": str(interview.id), "status": interview.status}


@router.post("/organizations/{organization_id}/interviews/{interview_id}/feedback", status_code=201)
def add_feedback(organization_id: UUID, interview_id: UUID, body: FeedbackInput,
                 _: None = Depends(require_csrf), user: User = Depends(require_recruiter_for_org),
                 db: Session = Depends(get_db)):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "Interview not found")
    application_for_org(db, organization_id, interview.application_id)
    feedback = InterviewFeedback(interview_id=interview_id, reviewer_id=user.id, **body.model_dump())
    db.add(feedback)
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Feedback already submitted")
    audit(db, organization_id, user.id, "interview.feedback", "interview", interview.id)
    db.commit()
    return {"id": str(feedback.id), "interview_id": str(interview_id)}


@router.get("/organizations/{organization_id}/interviews/{interview_id}/feedback")
def list_feedback(organization_id: UUID, interview_id: UUID, _: User = Depends(require_recruiter_for_org),
                  db: Session = Depends(get_db)):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "Interview not found")
    application_for_org(db, organization_id, interview.application_id)
    rows = db.execute(select(InterviewFeedback, User.full_name).join(User, InterviewFeedback.reviewer_id == User.id)
                      .where(InterviewFeedback.interview_id == interview_id)).all()
    return [{"id": str(f.id), "reviewer_id": str(f.reviewer_id), "reviewer": name, "score": f.score, "comments": f.comments}
            for f, name in rows]


@router.get("/organizations/{organization_id}/analytics")
def analytics(organization_id: UUID, _: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    must_org(db, organization_id)
    job_count = db.scalar(select(func.count(Job.id)).where(Job.organization_id == organization_id)) or 0
    app_count = db.scalar(select(func.count(Application.id)).join(Job).where(Job.organization_id == organization_id)) or 0
    interview_count = db.scalar(select(func.count(Interview.id)).join(Application).join(Job)
                                .where(Job.organization_id == organization_id)) or 0
    stages = dict(db.execute(select(Application.stage, func.count(Application.id)).join(Job)
                             .where(Job.organization_id == organization_id).group_by(Application.stage)).all())
    job_statuses = dict(db.execute(select(Job.status, func.count(Job.id))
                                   .where(Job.organization_id == organization_id).group_by(Job.status)).all())
    candidate_count = db.scalar(select(func.count(func.distinct(Application.candidate_id))).join(Job)
                                .where(Job.organization_id == organization_id)) or 0
    return {"organization_id": str(organization_id), "jobs": job_count,
            "applications": app_count, "interviews": interview_count, "candidates": candidate_count,
            "stages": stages, "job_statuses": job_statuses}


@router.get("/organizations/{organization_id}/audit-logs")
def audit_logs(organization_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    must_org(db, organization_id)
    if not user.is_platform_admin and not db.scalar(select(OrganizationMembership.id).where(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.role.in_(["owner", "admin"]))):
        raise HTTPException(403, "Admin role required")
    logs = db.scalars(select(AuditLog).where(AuditLog.organization_id == organization_id)
                      .order_by(AuditLog.created_at.desc()).limit(100)).all()
    return [{"id": str(log.id), "action": log.action, "target_type": log.target_type,
             "target_id": log.target_id, "created_at": log.created_at.isoformat() if log.created_at else None}
            for log in logs]
