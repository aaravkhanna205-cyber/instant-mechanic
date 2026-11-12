"""Interview Studio: scheduling, approval gate, consent gate, one-question session, human decision."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.interview_studio.questions import clean_questions, draft_questions, rule_questions
from app.models.schema import JobRequirement, Notification, User
from app.security.passwords import hash_password
from tests.test_recruitment_api import env, login, make_job  # noqa: F401  (env is a fixture)

BASE = "/api/interview-studio"
GOOD = [
    "Tell us about a recent project where you used Python at work. What was your part?",
    "Describe a difficult bug you fixed and how you confirmed the fix worked.",
    "How do you organise your work when several urgent tasks arrive together?",
]


def setup_interview(client, org, engine):
    admin = login(client, "admin@example.test")
    job_id = make_job(client, org, admin).json()["id"]
    with Session(engine) as db:
        db.add(JobRequirement(job_id=UUID(job_id), label="Python scripting for internal tools"))
        db.commit()
    candidate = login(client, "candidate@example.test")
    app_id = client.post(f"/api/recruitment/jobs/{job_id}/apply", headers=candidate).json()["id"]
    admin = login(client, "admin@example.test")
    created = client.post(f"/api/recruitment/organizations/{org}/interviews",
                          json={"application_id": app_id, "scheduled_at": "2031-01-01T10:00:00Z"}, headers=admin)
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_question_cleaning_blocks_personal_topics_and_duplicates():
    cleaned = clean_questions([
        "1. Describe a difficult problem you solved at work recently.",
        "describe a difficult problem you solved at work recently.",
        "Are you married and do you plan to have children soon?",
        "What is your religion and which caste do you belong to?",
        "too short",
        42,
    ])
    assert cleaned == ["Describe a difficult problem you solved at work recently."]
    rules = rule_questions("Python Developer", ["Python scripting"], 6)
    assert len(rules) == 6 and any("Python scripting" in q for q in rules)


def test_local_ai_drafts_are_filtered_and_fall_back_to_rules(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            reply = {"response": json.dumps({"questions": GOOD + ["How old are you and are you married?"]})}
            body = json.dumps(reply).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, *args): pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    monkeypatch.setattr(settings, "ollama_url", f"http://127.0.0.1:{server.server_port}")
    result = draft_questions("Python Developer", "Builds tools", ["Python"], 6)
    assert result["source"] == "local_ai" and result["questions"] == GOOD
    server.server_close()
    # Model unreachable: silently use the rule-based drafts.
    result = draft_questions("Python Developer", "Builds tools", ["Python"], 5)
    assert result["source"] == "rules" and len(result["questions"]) == 5


def test_full_interview_flow_with_gates(env):
    client, (org1, org2), engine = env
    interview_id = setup_interview(client, org1, engine)
    rec = f"{BASE}/organizations/{org1}/interviews/{interview_id}"
    me = f"{BASE}/me/interviews/{interview_id}"

    # Candidate cannot start: no consent yet, then no approved questions.
    cand = login(client, "candidate@example.test")
    listed = client.get(f"{BASE}/me/interviews").json()
    assert listed[0]["id"] == interview_id and listed[0]["consent_given"] is False
    assert client.get(f"{me}/session").status_code == 403
    assert client.post(f"{me}/consent", json={"granted": True}).status_code == 403  # CSRF required
    assert client.post(f"{me}/consent", json={"granted": True}, headers=cand).status_code == 200
    assert client.get(f"{me}/session").status_code == 409
    assert client.post(f"{me}/respond", json={"response": "maybe"}, headers=cand).status_code == 422
    assert client.post(f"{me}/respond", json={"response": "confirmed"}, headers=cand).json()["candidate_response"] == "confirmed"
    # A candidate cannot use recruiter endpoints.
    assert client.get(rec).status_code == 403
    assert client.put(f"{rec}/questions", json={"questions": GOOD}, headers=cand).status_code == 403

    # Recruiter of org1 cannot reach the interview through another organization.
    recruiter = login(client, "recruiter@example.test")
    assert client.get(f"{BASE}/organizations/{org2}/interviews/{interview_id}").status_code == 403
    drafted = client.post(f"{rec}/questions/draft", json={"count": 5}, headers=recruiter).json()
    assert drafted["source"] == "rules" and drafted["saved"] is False and len(drafted["questions"]) == 5
    assert client.get(f"{rec}/questions").json() == []  # drafting saved nothing
    bad = client.put(f"{rec}/questions", json={"questions": GOOD + ["What is your religion and your caste?"]}, headers=recruiter)
    assert bad.status_code == 422
    assert client.put(f"{rec}/questions", json={"questions": GOOD}).status_code == 403  # CSRF required
    approved = client.put(f"{rec}/questions", json={"questions": GOOD}, headers=recruiter)
    assert approved.status_code == 200 and [q["position"] for q in approved.json()] == [1, 2, 3]

    # Reschedule validation; a valid change asks the candidate to confirm again.
    assert client.patch(f"{rec}/schedule", json={"scheduled_at": "2020-01-01T10:00:00+05:30", "timezone": "Asia/Kolkata"}, headers=recruiter).status_code == 422
    assert client.patch(f"{rec}/schedule", json={"scheduled_at": "2031-02-01T10:00:00", "timezone": "Asia/Kolkata"}, headers=recruiter).status_code == 422
    assert client.patch(f"{rec}/schedule", json={"scheduled_at": "2031-02-01T10:00:00+05:30", "timezone": "Mars/Base"}, headers=recruiter).status_code == 422
    moved = client.patch(f"{rec}/schedule", json={"scheduled_at": "2031-02-01T10:00:00+05:30", "timezone": "Asia/Kolkata",
                                                  "duration_minutes": 45, "meeting_url": "https://meet.example.test/x"}, headers=recruiter)
    assert moved.status_code == 200, moved.text
    assert moved.json()["candidate_response"] == "pending" and moved.json()["scheduled_at"].startswith("2031-02-01T04:30:00")
    assert client.post(f"{rec}/decision", json={"decision": "advance", "note": "Too early"}, headers=recruiter).status_code == 409

    # Another candidate cannot see this interview.
    with Session(engine) as db:
        db.add(User(email="other@example.test", full_name="Other", password_hash=hash_password("strongpass123!")))
        db.commit()
    other = login(client, "other@example.test")
    assert client.get(f"{me}/session").status_code == 404
    assert client.post(f"{me}/consent", json={"granted": True}, headers=other).status_code == 404

    # One question at a time, in order, resumable.
    cand = login(client, "candidate@example.test")
    state = client.get(f"{me}/session").json()
    assert state["total"] == 3 and state["answered"] == 0 and state["current"]["position"] == 1
    first = state["current"]["id"]
    assert client.post(f"{me}/session/answers", json={"question_id": first, "answer": "x"}).status_code == 403  # CSRF
    state = client.post(f"{me}/session/answers", json={"question_id": first, "answer": "I built Python scripting tools for the workshop."}, headers=cand).json()
    assert state["answered"] == 1 and state["current"]["position"] == 2 and state["status"] == "in_progress"
    assert client.post(f"{me}/session/answers", json={"question_id": first, "answer": "again"}, headers=cand).status_code == 409
    assert client.post(f"{me}/session/complete", headers=cand).status_code == 409
    # Withdrawing consent blocks the session; granting it again resumes at the same question.
    client.post(f"{me}/consent", json={"granted": False}, headers=cand)
    assert client.get(f"{me}/session").status_code == 403
    client.post(f"{me}/consent", json={"granted": True}, headers=cand)
    resumed = client.get(f"{me}/session").json()
    assert resumed["current"]["position"] == 2
    state = client.post(f"{me}/session/answers", json={"question_id": resumed["current"]["id"], "answer": "I traced the fault with logs."}, headers=cand).json()
    state = client.post(f"{me}/session/answers", json={"question_id": state["current"]["id"], "answer": "I list tasks by deadline."}, headers=cand).json()
    assert state["all_answered"] is True and state["current"] is None
    assert client.post(f"{me}/session/complete", headers=cand).json()["status"] == "completed"
    assert client.get(f"{me}/session").status_code == 409  # closed

    # Recruiter: questions are locked, report has answers and no score, decision is human-entered.
    recruiter = login(client, "recruiter@example.test")
    assert client.put(f"{rec}/questions", json={"questions": GOOD}, headers=recruiter).status_code == 409
    assert client.patch(f"{rec}/schedule", json={"scheduled_at": "2031-03-01T10:00:00+05:30", "timezone": "Asia/Kolkata"}, headers=recruiter).status_code == 409
    report = client.get(f"{rec}/report").json()
    assert [item["answer"] for item in report["items"]][0].startswith("I built Python")
    assert report["decision"] is None and "score" not in json.dumps(report).lower()
    assert report["requirement_mentions"][0]["mentioned_in_answers"] is True
    assert client.post(f"{rec}/decision", json={"decision": "hire-now", "note": "Great"}, headers=recruiter).status_code == 422
    assert client.post(f"{rec}/decision", json={"decision": "advance", "note": "Clear, specific examples."}, headers=recruiter).status_code == 200
    assert client.post(f"{rec}/decision", json={"decision": "hold", "note": "Second reviewer needed."}, headers=recruiter).status_code == 200
    assert client.get(f"{rec}/report").json()["decision"]["decision"] == "hold"
    assert client.post(f"{rec}/cancel", headers=recruiter).status_code == 409
    with Session(engine) as db:
        kinds = set(db.scalars(select(Notification.kind)))
        assert "interview_rescheduled" in kinds


def test_cancel_notifies_and_closes(env):
    client, (org1, _), engine = env
    interview_id = setup_interview(client, org1, engine)
    admin = login(client, "admin@example.test")
    rec = f"{BASE}/organizations/{org1}/interviews/{interview_id}"
    assert client.post(f"{rec}/cancel", headers=admin).json()["status"] == "cancelled"
    cand = login(client, "candidate@example.test")
    client.post(f"{BASE}/me/interviews/{interview_id}/consent", json={"granted": True}, headers=cand)
    assert client.get(f"{BASE}/me/interviews/{interview_id}/session").status_code == 409
    assert client.post(f"{BASE}/me/interviews/{interview_id}/respond", json={"response": "confirmed"}, headers=cand).status_code == 409


def test_reminders_are_sent_once_for_interviews_in_the_next_day(env):
    from datetime import datetime, timedelta, timezone
    from app.models.schema import Interview
    from scripts.send_interview_reminders import send_reminders
    client, (org1, _), engine = env
    interview_id = setup_interview(client, org1, engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        assert send_reminders(db, now) == 0  # scheduled years ahead
        interview = db.get(Interview, UUID(interview_id))
        interview.scheduled_at = now + timedelta(hours=5)
        db.commit()
        assert send_reminders(db, now) == 1
        assert send_reminders(db, now) == 0  # not repeated
        assert "interview_reminder" in set(db.scalars(select(Notification.kind)))
