"""Candidate data-deletion requests with a human decision.

A signed-in candidate asks for their data to be deleted; a platform admin
approves or rejects. Nothing is erased automatically. Approval removes the
candidate's profile, applications, interviews, consents and notifications,
then anonymizes and deactivates the account. The audit trail keeps only the
opaque account id.

The legal wording and retention periods (India's DPDP Act) still need review
by a lawyer; this module only provides the workflow.
"""
import json
import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.api.candidate_import import UNUSABLE_PASSWORD
from app.api.management import csrf, log
from app.models.admin_tables import data_deletion_requests, import_rows, password_reset_requests
from app.models.schema import (
    Application, ApplicationStageHistory, CandidateProfile, Interview, InterviewFeedback,
    Notification, OrganizationMembership, Resume, User, UserConsent,
)
from app.security.dependencies import get_current_user, get_db, get_redis, require_platform_admin

router = APIRouter(prefix="/api/privacy", tags=["Privacy"])
admin_router = APIRouter(prefix="/api/admin-v3", tags=["Admin Phase 3"])

STAFF_ROLES = ("owner", "admin", "recruiter", "interviewer")
STATUSES = ("pending", "completed", "rejected", "cancelled")
requests_table = data_deletion_requests


class DeletionInput(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class DecisionInput(BaseModel):
    decision: str
    note: str | None = Field(default=None, max_length=1000)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _out(row) -> dict:
    return {"id": str(row.id), "status": row.status, "reason": row.reason, "created_at": _iso(row.created_at),
            "decided_at": _iso(row.decided_at), "decision_note": row.decision_note}


def _is_staff(db: Session, user: User) -> bool:
    return user.is_platform_admin or bool(db.scalar(select(OrganizationMembership.id).where(
        OrganizationMembership.user_id == user.id, OrganizationMembership.role.in_(STAFF_ROLES)).limit(1)))


def revoke_user_sessions(cache: Redis, user_id: UUID) -> None:
    """Sessions have no per-user index, so scan; fine at this deployment size."""
    for key in cache.scan_iter(match="imhire:sess:*", count=100):
        raw = cache.get(key)
        if not raw:
            continue
        try:
            if json.loads(raw).get("user_id") == str(user_id):
                cache.delete(key)
        except (ValueError, TypeError):
            pass


def erase_candidate_data(db: Session, user: User) -> None:
    """Delete a candidate's recruitment data and anonymize the account row."""
    profile_ids = db.scalars(select(CandidateProfile.id).where(CandidateProfile.user_id == user.id)).all()
    if profile_ids:
        application_ids = db.scalars(select(Application.id).where(Application.candidate_id.in_(profile_ids))).all()
        if application_ids:
            interview_ids = db.scalars(select(Interview.id).where(Interview.application_id.in_(application_ids))).all()
            if interview_ids:
                db.execute(delete(InterviewFeedback).where(InterviewFeedback.interview_id.in_(interview_ids)))
                db.execute(delete(Interview).where(Interview.id.in_(interview_ids)))
            db.execute(update(import_rows).where(import_rows.c.application_id.in_(application_ids)).values(application_id=None))
            db.execute(delete(ApplicationStageHistory).where(ApplicationStageHistory.application_id.in_(application_ids)))
            db.execute(delete(Application).where(Application.id.in_(application_ids)))
        db.execute(delete(Resume).where(Resume.candidate_id.in_(profile_ids)))
        db.execute(delete(CandidateProfile).where(CandidateProfile.id.in_(profile_ids)))
    db.execute(delete(UserConsent).where(UserConsent.user_id == user.id))
    db.execute(delete(Notification).where(Notification.user_id == user.id))
    db.execute(delete(OrganizationMembership).where(OrganizationMembership.user_id == user.id))
    db.execute(delete(password_reset_requests).where(password_reset_requests.c.user_id == user.id))
    db.execute(update(import_rows).where(import_rows.c.user_id == user.id).values(data={}))
    user.email = f"deleted-{user.id}@deleted.invalid"
    user.full_name = "Deleted account"
    user.password_hash = UNUSABLE_PASSWORD
    user.active = False


@router.get("/deletion-requests/me")
def my_deletion_requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(requests_table).where(requests_table.c.user_id == user.id)
                      .order_by(requests_table.c.created_at.desc())).all()
    return [_out(row) for row in rows]


@router.post("/deletion-requests", status_code=201)
def request_deletion(body: DeletionInput, _: None = Depends(csrf), user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    if _is_staff(db, user):
        raise HTTPException(403, "Staff accounts are removed by a platform administrator")
    if db.scalar(select(requests_table.c.id).where(requests_table.c.user_id == user.id,
                                                   requests_table.c.status == "pending").limit(1)):
        raise HTTPException(409, "A deletion request is already waiting for review")
    request_id = uuid.uuid4()
    db.execute(insert(requests_table).values(id=request_id, user_id=user.id, status="pending",
                                             reason=(body.reason or "").strip() or None))
    log(db, user.id, "privacy.deletion_requested", target=request_id)
    db.commit()
    return _out(db.execute(select(requests_table).where(requests_table.c.id == request_id)).one())


@router.post("/deletion-requests/{request_id}/cancel")
def cancel_deletion(request_id: UUID, _: None = Depends(csrf), user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    row = db.execute(select(requests_table).where(requests_table.c.id == request_id,
                                                  requests_table.c.user_id == user.id).with_for_update()).first()
    if row is None:
        raise HTTPException(404, "Request not found")
    if row.status != "pending":
        raise HTTPException(409, "Only a pending request can be cancelled")
    db.execute(update(requests_table).where(requests_table.c.id == request_id)
               .values(status="cancelled", decided_at=datetime.now(timezone.utc)))
    log(db, user.id, "privacy.deletion_cancelled", target=request_id)
    db.commit()
    return {"id": str(request_id), "status": "cancelled"}


@admin_router.get("/deletion-requests")
def list_deletion_requests(status: str | None = None, _: User = Depends(require_platform_admin),
                           db: Session = Depends(get_db)):
    if status is not None and status not in STATUSES:
        raise HTTPException(422, "Invalid status")
    query = (select(requests_table, User.email, User.full_name)
             .join(User, User.id == requests_table.c.user_id)
             .order_by(requests_table.c.created_at.desc()).limit(200))
    if status:
        query = query.where(requests_table.c.status == status)
    return [{**_out(row), "user_id": str(row.user_id), "email": row.email, "full_name": row.full_name}
            for row in db.execute(query).all()]


@admin_router.post("/deletion-requests/{request_id}/decision")
def decide_deletion(request_id: UUID, body: DecisionInput, _: None = Depends(csrf),
                    admin: User = Depends(require_platform_admin), db: Session = Depends(get_db),
                    cache: Redis = Depends(get_redis)):
    if body.decision not in ("approve", "reject"):
        raise HTTPException(422, "Decision must be approve or reject")
    row = db.execute(select(requests_table).where(requests_table.c.id == request_id).with_for_update()).first()
    if row is None:
        raise HTTPException(404, "Request not found")
    if row.status != "pending":
        raise HTTPException(409, "This request has already been decided")
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(404, "Account not found")
    status = "rejected"
    if body.decision == "approve":
        if _is_staff(db, user):
            raise HTTPException(409, "Remove this person's staff roles before deleting their data")
        erase_candidate_data(db, user)
        status = "completed"
    db.execute(update(requests_table).where(requests_table.c.id == request_id).values(
        status=status, decided_by_id=admin.id, decided_at=datetime.now(timezone.utc),
        decision_note=(body.note or "").strip() or None))
    log(db, admin.id, f"privacy.deletion_{status}", target=row.user_id, extra={"request_id": str(request_id)})
    db.commit()
    if status == "completed":
        revoke_user_sessions(cache, row.user_id)
    return {"id": str(request_id), "status": status}
