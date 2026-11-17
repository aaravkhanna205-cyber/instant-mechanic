"""Notifications: in-app for everyone, email for candidates.

Emails use the same delivery setting as Phase 6 (PHASE6_DELIVERY_MODE): in "outbox" mode
they are only stored and marked "outbox" (nothing is sent); in "smtp" mode they are sent.
"""
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.schema import Notification, OrganizationMembership, User
from app.security.roles import RECRUITING

EMAIL_BATCH = 20


def notify(db: Session, user_id: UUID | None, kind: str, message: str, *, organization_id: UUID | None = None,
           link: str | None = None, email: bool = False) -> Notification | None:
    """Adds a notification to the session; the caller commits."""
    if not user_id:
        return None
    row = Notification(user_id=user_id, kind=kind[:60], message=message[:2000], organization_id=organization_id,
                       link=(link or None) and link[:300], email_status='pending' if email else None)
    db.add(row)
    return row


def notify_team(db: Session, organization_id: UUID, kind: str, message: str, *, link: str | None = None,
                exclude: UUID | None = None) -> int:
    """In-app notification to everyone who recruits in this organization."""
    user_ids = set(db.scalars(select(OrganizationMembership.user_id).join(User, User.id == OrganizationMembership.user_id)
                              .where(OrganizationMembership.organization_id == organization_id,
                                     OrganizationMembership.role.in_(RECRUITING), User.active.is_(True))).all())
    user_ids.discard(exclude)
    for user_id in user_ids:
        notify(db, user_id, kind, message, organization_id=organization_id, link=link)
    return len(user_ids)


def notify_platform_admins(db: Session, kind: str, message: str, *, link: str | None = None) -> int:
    ids = db.scalars(select(User.id).where(User.is_platform_admin.is_(True), User.active.is_(True))).all()
    for user_id in ids:
        notify(db, user_id, kind, message, link=link)
    return len(ids)


def _email_body(user: User, row: Notification, site_url: str) -> str:
    link = f'\n\nOpen: {site_url.rstrip("/")}{row.link}' if row.link and site_url else ''
    return (f'Hello {user.full_name.split(" ")[0] if user.full_name else ""},\n\n{row.message}{link}\n\n'
            'Instant Mechanic Hire\n(You receive this because you applied for a job with Instant Mechanic.)')


def send_pending_emails(db: Session, mode: str, deliver, site_url: str = '', limit: int = EMAIL_BATCH) -> int:
    """Called by the Phase 6 worker. `deliver` is the worker's own send function (outbox or SMTP)."""
    rows = db.scalars(select(Notification).where(Notification.email_status == 'pending')
                      .order_by(Notification.created_at).limit(limit)).all()
    for row in rows:
        user = db.get(User, row.user_id)
        if user is None or not user.active or user.email.endswith('@deleted.invalid'):
            row.email_status = 'skipped'
            continue
        try:
            status, _ = deliver(user.email, 'Update on your application · Instant Mechanic', _email_body(user, row, site_url), mode)
            row.email_status = 'sent' if status == 'smtp_accepted' else 'outbox'
            row.email_error = None
        except Exception as exc:  # noqa: BLE001 - recorded on the row and retried never; shown in the email log
            row.email_status = 'failed'
            row.email_error = f'{type(exc).__name__}: {exc}'[:300]
        row.emailed_at = datetime.now(timezone.utc)
        db.commit()
    return len(rows)


def out(row: Notification) -> dict:
    return {'id': str(row.id), 'kind': row.kind, 'message': row.message, 'link': row.link,
            'organization_id': str(row.organization_id) if row.organization_id else None,
            'read': row.read_at is not None, 'email_status': row.email_status,
            'created_at': row.created_at.isoformat() if row.created_at else None}
