"""Data retention: find candidates whose applications all closed long ago, and erase them on request.

Erasing reuses the Phase 3 privacy routine and also removes resume files from disk,
which the database cascade alone leaves behind.
"""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from app.models.schema import (Application, ApplicationStageHistory, CandidateProfile, Interview, OrganizationMembership,
                               User)
from app.security.roles import STAFF

CLOSED = ('hired', 'rejected', 'withdrawn')
log = logging.getLogger(__name__)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def eligible(db: Session, days: int, now: datetime | None = None) -> list[dict]:
    """Candidates (never staff or Super Admin) with applications that are all closed and no activity for `days`."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    staff = set(db.scalars(select(OrganizationMembership.user_id).where(OrganizationMembership.role.in_(STAFF))).all())
    rows = db.execute(select(User.id, User.full_name, User.email, CandidateProfile.id)
                      .join(CandidateProfile, CandidateProfile.user_id == User.id)
                      .where(User.active.is_(True), User.is_platform_admin.is_(False))).all()
    out = []
    for user_id, name, email, profile_id in rows:
        if user_id in staff or email.endswith('@deleted.invalid'):
            continue
        apps = db.execute(select(Application.id, Application.stage, Application.applied_at)
                          .where(Application.candidate_id == profile_id)).all()
        if not apps or any(stage not in CLOSED for _, stage, _ in apps):
            continue
        ids = [a[0] for a in apps]
        last = max(filter(None, [_aware(a[2]) for a in apps]
                          + [_aware(db.scalar(select(func.max(ApplicationStageHistory.changed_at))
                                              .where(ApplicationStageHistory.application_id.in_(ids))))]
                          + [_aware(db.scalar(select(func.max(Interview.scheduled_at))
                                              .where(Interview.application_id.in_(ids))))]), default=None)
        if last is None or last < cutoff:
            out.append({'user_id': str(user_id), 'full_name': name, 'email': email,
                        'applications': len(apps), 'last_activity': last.isoformat() if last else None})
    return sorted(out, key=lambda r: r['last_activity'] or '')


def resume_files(db: Session, user_id: UUID) -> list[tuple[UUID, str]]:
    try:
        rows = db.execute(text('SELECT id, file_ext FROM phase4_documents WHERE user_id = :u'), {'u': user_id}).all()
    except Exception:  # noqa: BLE001 - table absent in some test databases
        db.rollback()
        return []
    return [(UUID(str(r[0])), r[1]) for r in rows]


def remove_files(files: list[tuple[UUID, str]]) -> int:
    """Best effort after the database change is committed; a missing file is fine."""
    from app.phase4_ai.storage import path_for
    removed = 0
    for document_id, ext in files:
        for suffix in {ext, 'txt'}:
            try:
                path_for(document_id, suffix).unlink(missing_ok=True)
                removed += 1
            except (ValueError, OSError):
                log.warning('Could not remove resume file %s.%s', document_id, suffix)
    return removed
