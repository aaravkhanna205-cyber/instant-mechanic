"""Phase 7 API: notifications, team and roles, search, reports, exports, retention and Super Admin controls."""
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from redis import Redis
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session
from app.api.recruitment import require_csrf
from app.models.schema import Application, AuditLog, Notification, Organization, OrganizationMembership, User
from app.security.dependencies import (get_current_user, get_db, get_redis, require_full_access_for_org,
                                       require_platform_admin, require_recruiter_for_org)
from app.security.roles import ALL_ROLES, FULL_ACCESS, TEAM_ROLES, role_list
from . import reports, retention
from .notifications import out as notification_out

me = APIRouter(prefix='/api/notifications', tags=['Phase 7 Notifications'])
org = APIRouter(prefix='/api/phase7/organizations/{organization_id}', tags=['Phase 7 Organization'])
admin = APIRouter(prefix='/api/phase7/admin', tags=['Phase 7 Super Admin'])
public = APIRouter(prefix='/api/phase7', tags=['Phase 7'])


def _audit(db: Session, org_id: UUID | None, actor: UUID, action: str, target: str | None = None, extra: dict | None = None):
    db.add(AuditLog(organization_id=org_id, actor_id=actor, action=action, target_type='phase7',
                    target_id=target, context=extra or {}))


# ------------------------------------------------------------------ roles
@public.get('/roles')
def roles(_: User = Depends(get_current_user)):
    return role_list()


# ------------------------------------------------------------------ my notifications
@me.get('')
def my_notifications(unread: bool = False, limit: int = Query(default=50, ge=1, le=200),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(Notification).where(Notification.user_id == user.id)
    if unread:
        query = query.where(Notification.read_at.is_(None))
    return [notification_out(n) for n in db.scalars(query.order_by(Notification.created_at.desc()).limit(limit)).all()]


@me.get('/unread-count')
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {'unread': db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id,
                                                                         Notification.read_at.is_(None))) or 0}


@me.post('/{notification_id}/read')
def mark_read(notification_id: UUID, _: None = Depends(require_csrf), user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    row = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if row is None:
        raise HTTPException(404, 'Notification not found')
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        db.commit()
    return notification_out(row)


@me.post('/read-all')
def mark_all_read(_: None = Depends(require_csrf), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
                        .values(read_at=datetime.now(timezone.utc)))
    db.commit()
    return {'updated': result.rowcount or 0}


# ------------------------------------------------------------------ team (full-access roles)
class TeamAdd(BaseModel):
    email: EmailStr
    role: str


class TeamChange(BaseModel):
    role: str


def _member_rows(db: Session, organization_id: UUID):
    return db.execute(select(OrganizationMembership, User).join(User, User.id == OrganizationMembership.user_id)
                      .where(OrganizationMembership.organization_id == organization_id,
                             OrganizationMembership.role.in_(TEAM_ROLES))
                      .order_by(User.full_name)).all()


def _member_out(m: OrganizationMembership, u: User) -> dict:
    return {'user_id': str(u.id), 'email': u.email, 'full_name': u.full_name, 'role': m.role, 'active': u.active,
            'is_platform_admin': u.is_platform_admin, 'full_access': m.role in FULL_ACCESS}


def _actor_roles(db: Session, user: User, organization_id: UUID) -> set[str]:
    return set(db.scalars(select(OrganizationMembership.role).where(
        OrganizationMembership.user_id == user.id, OrganizationMembership.organization_id == organization_id)).all())


def _check_change(db: Session, actor: User, organization_id: UUID, target: OrganizationMembership | None,
                  new_role: str | None) -> None:
    """Rules that keep the organization manageable and stop people raising their own access."""
    actor_is_owner = actor.is_platform_admin or 'owner' in _actor_roles(db, actor, organization_id)
    if new_role is not None and new_role not in TEAM_ROLES:
        raise HTTPException(422, f'Role must be one of: {", ".join(TEAM_ROLES)}')
    if new_role == 'owner' and not actor_is_owner:
        raise HTTPException(403, 'Only an owner or the Super Admin can make someone an owner')
    if target is None:
        return
    if target.user_id == actor.id and not actor.is_platform_admin:
        raise HTTPException(403, 'You cannot change your own role. Ask another manager or the Super Admin.')
    if target.role == 'owner' and not actor_is_owner:
        raise HTTPException(403, 'Only an owner or the Super Admin can change an owner')
    losing_full = target.role in FULL_ACCESS and (new_role is None or new_role not in FULL_ACCESS)
    if losing_full:
        others = db.scalar(select(func.count(OrganizationMembership.id)).join(User, User.id == OrganizationMembership.user_id)
                           .where(OrganizationMembership.organization_id == organization_id,
                                  OrganizationMembership.role.in_(FULL_ACCESS), User.active.is_(True),
                                  OrganizationMembership.id != target.id)) or 0
        if others == 0:
            raise HTTPException(409, 'This is the last person with full access. Give someone else full access first.')


@org.get('/team')
def team(organization_id: UUID, _: User = Depends(require_full_access_for_org), db: Session = Depends(get_db)):
    return {'members': [_member_out(m, u) for m, u in _member_rows(db, organization_id)], 'roles': role_list()}


@org.post('/team', status_code=201)
def team_add(organization_id: UUID, body: TeamAdd, _: None = Depends(require_csrf),
             actor: User = Depends(require_full_access_for_org), db: Session = Depends(get_db)):
    _check_change(db, actor, organization_id, None, body.role)
    user = db.scalar(select(User).where(func.lower(User.email) == str(body.email).lower().strip()))
    if user is None or not user.active:
        raise HTTPException(404, 'No active account with this email. Ask them to register first, then add them.')
    existing = db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == user.id,
                                                              OrganizationMembership.organization_id == organization_id))
    if existing and existing.role in TEAM_ROLES:
        raise HTTPException(409, 'Already in the team. Change their role instead.')
    if existing:  # a candidate membership becomes a staff role
        existing.role = body.role
        member = existing
    else:
        member = OrganizationMembership(user_id=user.id, organization_id=organization_id, role=body.role)
        db.add(member)
    _audit(db, organization_id, actor.id, 'team.add', str(user.id), {'role': body.role})
    from .notifications import notify
    org_name = db.scalar(select(Organization.name).where(Organization.id == organization_id)) or 'the organization'
    notify(db, user.id, 'team_added', f'You were added to {org_name} as {dict((r["role"], r["label"]) for r in role_list())[body.role]}.',
           organization_id=organization_id, link='/dashboard')
    db.commit()
    return _member_out(member, user)


@org.patch('/team/{user_id}')
def team_change(organization_id: UUID, user_id: UUID, body: TeamChange, _: None = Depends(require_csrf),
                actor: User = Depends(require_full_access_for_org), db: Session = Depends(get_db)):
    member = db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == user_id,
                                                            OrganizationMembership.organization_id == organization_id,
                                                            OrganizationMembership.role.in_(TEAM_ROLES)))
    if member is None:
        raise HTTPException(404, 'Team member not found')
    _check_change(db, actor, organization_id, member, body.role)
    previous, member.role = member.role, body.role
    _audit(db, organization_id, actor.id, 'team.role_change', str(user_id), {'from': previous, 'to': body.role})
    db.commit()
    return _member_out(member, db.get(User, user_id))


@org.delete('/team/{user_id}')
def team_remove(organization_id: UUID, user_id: UUID, _: None = Depends(require_csrf),
                actor: User = Depends(require_full_access_for_org), db: Session = Depends(get_db)):
    member = db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == user_id,
                                                            OrganizationMembership.organization_id == organization_id,
                                                            OrganizationMembership.role.in_(TEAM_ROLES)))
    if member is None:
        raise HTTPException(404, 'Team member not found')
    _check_change(db, actor, organization_id, member, None)
    db.delete(member)
    _audit(db, organization_id, actor.id, 'team.remove', str(user_id), {'role': member.role})
    db.commit()
    return {'removed': True}


# ------------------------------------------------------------------ emails sent to candidates (full access)
@org.get('/emails')
def emails(organization_id: UUID, status: str | None = None, limit: int = Query(default=100, ge=1, le=500),
           _: User = Depends(require_full_access_for_org), db: Session = Depends(get_db)):
    query = (select(Notification, User.full_name, User.email).join(User, User.id == Notification.user_id)
             .where(Notification.organization_id == organization_id, Notification.email_status.is_not(None)))
    if status:
        query = query.where(Notification.email_status == status)
    rows = db.execute(query.order_by(Notification.created_at.desc()).limit(limit)).all()
    return [{**notification_out(n), 'to_name': name, 'to_email': email, 'emailed_at': n.emailed_at.isoformat() if n.emailed_at else None,
             'email_error': n.email_error} for n, name, email in rows]


# ------------------------------------------------------------------ search and reports
@org.get('/applications/search')
def search(organization_id: UUID, q: str | None = None, stage: str | None = None, job_id: UUID | None = None,
           page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=5, le=100),
           _: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    query = reports.application_query(organization_id, q, stage, job_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(query.order_by(Application.applied_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {'items': [reports.application_row(r) for r in rows], 'total': total, 'page': page, 'page_size': page_size,
            'pages': max(1, -(-total // page_size))}


@org.get('/reports/summary')
def report_summary(organization_id: UUID, days: int = Query(default=30, ge=7, le=365),
                   _: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    return reports.summary(db, organization_id, days)


@org.get('/exports/{kind}.csv')
def export_csv(organization_id: UUID, kind: str, q: str | None = None, stage: str | None = None, job_id: UUID | None = None,
               actor: User = Depends(require_full_access_for_org), db: Session = Depends(get_db)):
    """Personal data, so only full-access roles may export. Each export is written to the audit log."""
    if kind not in ('applications', 'candidates', 'interviews'):
        raise HTTPException(404, 'Unknown export')
    body, count = reports.export(db, organization_id, kind, q, stage, job_id)
    _audit(db, organization_id, actor.id, 'export.csv', None, {'kind': kind, 'rows': count})
    db.commit()
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return Response(content=body.encode('utf-8'), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="instant-mechanic-{kind}-{stamp}.csv"',
                             'Cache-Control': 'no-store'})


# ------------------------------------------------------------------ Super Admin
class PlatformAdminInput(BaseModel):
    value: bool


class RetentionApply(BaseModel):
    days: int = Field(ge=90, le=3650)
    expected_count: int = Field(ge=1)


@admin.post('/users/{user_id}/platform-admin')
def set_platform_admin(user_id: UUID, body: PlatformAdminInput, _: None = Depends(require_csrf),
                       actor: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    if user_id == actor.id:
        raise HTTPException(403, 'You cannot change your own Super Admin access')
    user = db.get(User, user_id)
    if user is None or not user.active:
        raise HTTPException(404, 'Active account not found')
    if not body.value and user.is_platform_admin:
        others = db.scalar(select(func.count(User.id)).where(User.is_platform_admin.is_(True), User.active.is_(True),
                                                            User.id != user_id)) or 0
        if others == 0:
            raise HTTPException(409, 'There must always be at least one Super Admin')
    user.is_platform_admin = body.value
    _audit(db, None, actor.id, 'admin.platform_admin_' + ('granted' if body.value else 'removed'), str(user_id))
    db.commit()
    return {'user_id': str(user_id), 'is_platform_admin': user.is_platform_admin}


@admin.get('/retention')
def retention_preview(days: int = Query(default=365, ge=90, le=3650), _: User = Depends(require_platform_admin),
                      db: Session = Depends(get_db)):
    rows = retention.eligible(db, days)
    return {'days': days, 'count': len(rows), 'candidates': rows[:200]}


@admin.post('/retention/apply')
def retention_apply(body: RetentionApply, _: None = Depends(require_csrf), actor: User = Depends(require_platform_admin),
                    db: Session = Depends(get_db), cache: Redis = Depends(get_redis)):
    from app.api.privacy import erase_candidate_data, revoke_user_sessions
    rows = retention.eligible(db, body.days)
    if len(rows) != body.expected_count:
        raise HTTPException(409, f'The list changed: {len(rows)} candidates now match. Check the list again before deleting.')
    files, ids = [], []
    for row in rows:
        user = db.get(User, UUID(row['user_id']))
        files += retention.resume_files(db, user.id)
        erase_candidate_data(db, user)
        ids.append(user.id)
    _audit(db, None, actor.id, 'retention.erased', None, {'days': body.days, 'count': len(ids)})
    db.commit()
    for user_id in ids:
        revoke_user_sessions(cache, user_id)
    retention.remove_files(files)
    return {'erased': len(ids)}


from app.phase8.monitoring import summary as server_error_summary  # noqa: E402


@admin.get('/health')
def health(_: User = Depends(require_platform_admin), db: Session = Depends(get_db), cache: Redis = Depends(get_redis)):
    def count(sql: str) -> int | None:
        try:
            return int(db.execute(text(sql)).scalar() or 0)
        except Exception:  # noqa: BLE001 - a missing optional table shows as "not available"
            db.rollback()
            return None
    try:
        redis_ok = bool(cache.ping())
    except Exception:  # noqa: BLE001
        redis_ok = False
    worker = None
    try:
        worker = bool(cache.exists('imhire:p6:worker-lease'))
    except Exception:  # noqa: BLE001
        pass
    return {
        'database': True, 'redis': redis_ok, 'worker_running_now': worker,
        'users': count('SELECT count(*) FROM users WHERE active'),
        'organizations': count('SELECT count(*) FROM organizations'),
        'emails_waiting': count("SELECT count(*) FROM notifications WHERE email_status = 'pending'"),
        'emails_failed': count("SELECT count(*) FROM notifications WHERE email_status = 'failed'"),
        'resumes_waiting': count("SELECT count(*) FROM phase4_documents WHERE status = 'queued'"),
        'resumes_failed': count("SELECT count(*) FROM phase4_documents WHERE status = 'failed'"),
        'agent_messages_queued': count("SELECT count(*) FROM phase6_proposals WHERE state = 'queued'"),
        'workflows_failed': count("SELECT count(*) FROM phase6_workflow_runs WHERE status = 'failed'"),
        'deletion_requests_pending': count("SELECT count(*) FROM data_deletion_requests WHERE status = 'pending'"),
        'server_errors': server_error_summary(db),
        'checked_at': datetime.now(timezone.utc).isoformat(),
    }


ROUTERS = (me, org, admin, public)
__all__ = ['ROUTERS', 'ALL_ROLES']
