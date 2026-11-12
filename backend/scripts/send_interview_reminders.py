"""Create in-app reminders for interviews starting within the next 24 hours.

Safe to run as often as you like: each interview is reminded once per scheduled time.
    python -m scripts.send_interview_reminders
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.schema import Application, CandidateProfile, Interview, Job, Notification
from app.security.dependencies import session_factory


def send_reminders(db, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    rows = db.execute(
        select(Interview, Job.title, CandidateProfile.user_id)
        .join(Application, Interview.application_id == Application.id)
        .join(Job, Application.job_id == Job.id)
        .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
        .where(Interview.status == "scheduled", Interview.reminder_sent_at.is_(None),
               Interview.candidate_response != "declined",
               Interview.scheduled_at > now, Interview.scheduled_at <= now + timedelta(hours=24))
    ).all()
    for interview, title, candidate_user_id in rows:
        message = f"Reminder: your interview for {title} is within the next 24 hours. Open your portal for the time and link."
        db.add(Notification(user_id=candidate_user_id, kind="interview_reminder", message=message))
        if interview.interviewer_id:
            db.add(Notification(user_id=interview.interviewer_id, kind="interview_reminder",
                                message=f"Reminder: you have an interview for {title} within the next 24 hours."))
        interview.reminder_sent_at = now
    db.commit()
    return len(rows)


def main():
    with session_factory()() as db:
        print(f"Interview reminders created: {send_reminders(db)}")


if __name__ == "__main__":
    main()
