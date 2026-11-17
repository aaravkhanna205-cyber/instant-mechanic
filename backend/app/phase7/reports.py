"""Hiring reports and CSV exports for one organization."""
import csv
import io
import statistics
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.models.schema import (Application, ApplicationStageHistory, CandidateProfile, Interview, Job, User)

FUNNEL = ['applied', 'screening', 'shortlisted', 'trade_test', 'interview', 'offer', 'hired']
OPEN_INTERVIEW = ('scheduled', 'in_progress')


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _pct(part: int, whole: int) -> float | None:
    return round(part * 100 / whole, 1) if whole else None


def summary(db: Session, organization_id: UUID, days: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    jobs = {j.id: j for j in db.scalars(select(Job).where(Job.organization_id == organization_id)).all()}
    apps = db.execute(select(Application.id, Application.job_id, Application.stage, Application.applied_at)
                      .join(Job, Job.id == Application.job_id).where(Job.organization_id == organization_id)).all()
    history: dict = {}
    hired_at: dict = {}
    changes = db.execute(select(ApplicationStageHistory.application_id, ApplicationStageHistory.new_stage,
                                ApplicationStageHistory.changed_at, ApplicationStageHistory.changed_by_id)
                         .join(Application, Application.id == ApplicationStageHistory.application_id)
                         .join(Job, Job.id == Application.job_id).where(Job.organization_id == organization_id)).all()
    activity: dict = {}
    for app_id, stage, changed_at, by in changes:
        history.setdefault(app_id, set()).add(stage)
        changed_at = _aware(changed_at)
        if stage == 'hired' and changed_at and (app_id not in hired_at or changed_at < hired_at[app_id]):
            hired_at[app_id] = changed_at
        if by and changed_at and changed_at >= start and stage != 'applied':
            activity[by] = activity.get(by, 0) + 1

    in_period = [a for a in apps if _aware(a[3]) and _aware(a[3]) >= start]
    reached = {stage: 0 for stage in FUNNEL}
    by_stage: dict[str, int] = {}
    for app_id, _, stage, _ in in_period:
        by_stage[stage] = by_stage.get(stage, 0) + 1
        seen = history.get(app_id, set()) | {stage, 'applied'}
        for s in FUNNEL:
            if s in seen:
                reached[s] += 1
    # A later stage implies the earlier ones were passed, even if a step was skipped.
    for i in range(len(FUNNEL) - 2, -1, -1):
        reached[FUNNEL[i]] = max(reached[FUNNEL[i]], reached[FUNNEL[i + 1]])

    applied_at = {a[0]: _aware(a[3]) for a in apps}
    hire_days = [(t - applied_at[a]).total_seconds() / 86400 for a, t in hired_at.items()
                 if t >= start and applied_at.get(a) and t >= applied_at[a]]

    interviews = db.execute(select(Interview.status, Interview.scheduled_at)
                            .join(Application, Application.id == Interview.application_id)
                            .join(Job, Job.id == Application.job_id).where(Job.organization_id == organization_id)).all()
    due = [(s, _aware(t)) for s, t in interviews if _aware(t) and start <= _aware(t) <= now]
    interview_counts: dict[str, int] = {}
    for status_, _ in due:
        interview_counts[status_] = interview_counts.get(status_, 0) + 1
    completed = interview_counts.get('completed', 0)

    per_job = []
    for job_id, job in jobs.items():
        seen = [history.get(a[0], set()) | {a[2]} for a in in_period if a[1] == job_id]
        per_job.append({'job_id': str(job_id), 'title': job.title, 'status': job.status, 'applications': len(seen),
                        'interviewed': sum(1 for s in seen if {'interview', 'offer', 'hired'} & s),
                        'offers': sum(1 for s in seen if {'offer', 'hired'} & s),
                        'hired': sum(1 for s in seen if 'hired' in s)})
    per_job.sort(key=lambda j: (-j['applications'], j['title']))
    names = dict(db.execute(select(User.id, User.full_name).where(User.id.in_(list(activity) or [None]))).all())
    return {
        'days': days, 'from': start.isoformat(), 'to': now.isoformat(),
        'applications': len(in_period), 'open_jobs': sum(1 for j in jobs.values() if j.status == 'published'),
        'by_stage': by_stage,
        'funnel': [{'stage': s, 'count': reached[s]} for s in FUNNEL],
        'conversion': {'applied_to_interview': _pct(reached['interview'], reached['applied']),
                       'interview_to_offer': _pct(reached['offer'], reached['interview']),
                       'offer_to_hired': _pct(reached['hired'], reached['offer'])},
        'time_to_hire': {'hires': len(hire_days),
                         'average_days': round(statistics.mean(hire_days), 1) if hire_days else None,
                         'median_days': round(statistics.median(hire_days), 1) if hire_days else None},
        'interviews': {'due': len(due), 'completed': completed, 'by_status': interview_counts,
                       'completion_rate': _pct(completed, len(due))},
        'jobs': per_job,
        'activity': sorted([{'name': names.get(uid, 'Unknown'), 'stage_changes': n} for uid, n in activity.items()],
                           key=lambda r: -r['stage_changes']),
    }


def application_query(organization_id: UUID, q: str | None = None, stage: str | None = None, job_id: UUID | None = None):
    query = (select(Application.id, Application.stage, Application.applied_at, Job.id, Job.title, User.full_name, User.email,
                    CandidateProfile.phone, CandidateProfile.city)
             .join(Job, Job.id == Application.job_id)
             .join(CandidateProfile, CandidateProfile.id == Application.candidate_id)
             .join(User, User.id == CandidateProfile.user_id)
             .where(Job.organization_id == organization_id))
    if stage:
        query = query.where(Application.stage == stage)
    if job_id:
        query = query.where(Job.id == job_id)
    if q and q.strip():
        like = f'%{q.strip()[:100].lower()}%'
        query = query.where(or_(func.lower(User.full_name).like(like), func.lower(User.email).like(like),
                                func.lower(Job.title).like(like), func.lower(func.coalesce(CandidateProfile.city, '')).like(like),
                                func.lower(func.coalesce(CandidateProfile.phone, '')).like(like)))
    return query


def application_row(r) -> dict:
    return {'id': str(r[0]), 'stage': r[1], 'applied_at': r[2].isoformat() if r[2] else None, 'job_id': str(r[3]),
            'job_title': r[4], 'candidate_name': r[5], 'candidate_email': r[6], 'phone': r[7], 'city': r[8]}


def _safe(value) -> str:
    """Stops spreadsheet programs from running a cell as a formula."""
    text_ = '' if value is None else str(value)
    return "'" + text_ if text_[:1] in ('=', '+', '-', '@', '\t', '\r') else text_


def to_csv(header: list[str], rows: list[list]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow([_safe(v) for v in row])
    return '﻿' + buffer.getvalue()  # BOM so Excel reads Hindi and other non-English names correctly


def export(db: Session, organization_id: UUID, kind: str, q: str | None = None, stage: str | None = None,
           job_id: UUID | None = None) -> tuple[str, int]:
    if kind == 'applications':
        rows = db.execute(application_query(organization_id, q, stage, job_id)
                          .order_by(Application.applied_at.desc()).limit(10000)).all()
        return to_csv(['Candidate', 'Email', 'Phone', 'City', 'Job', 'Stage', 'Applied on'],
                      [[r[5], r[6], r[7], r[8], r[4], r[1], r[2].date().isoformat() if r[2] else ''] for r in rows]), len(rows)
    if kind == 'candidates':
        # Counted per profile first: PostgreSQL cannot group by the JSON skills column.
        counts = db.execute(select(Application.candidate_id, func.count(Application.id), func.max(Application.applied_at))
                            .join(Job, Job.id == Application.job_id).where(Job.organization_id == organization_id)
                            .group_by(Application.candidate_id).limit(10000)).all()
        stats = {c[0]: (c[1], c[2]) for c in counts}
        people = db.execute(select(CandidateProfile.id, User.full_name, User.email, CandidateProfile.phone,
                                   CandidateProfile.city, CandidateProfile.skills)
                            .join(User, User.id == CandidateProfile.user_id)
                            .where(CandidateProfile.id.in_(list(stats) or [None])).order_by(User.full_name)).all()
        rows = [[p[1], p[2], p[3], p[4], ', '.join(p[5].keys()) if isinstance(p[5], dict) else '', stats[p[0]][0],
                 stats[p[0]][1].date().isoformat() if stats[p[0]][1] else ''] for p in people]
        return to_csv(['Candidate', 'Email', 'Phone', 'City', 'Skills', 'Applications', 'Last applied'], rows), len(rows)
    if kind == 'interviews':
        rows = db.execute(select(Interview.scheduled_at, Interview.status, Interview.candidate_response, Job.title, User.full_name,
                                 User.email)
                          .join(Application, Application.id == Interview.application_id)
                          .join(Job, Job.id == Application.job_id)
                          .join(CandidateProfile, CandidateProfile.id == Application.candidate_id)
                          .join(User, User.id == CandidateProfile.user_id)
                          .where(Job.organization_id == organization_id)
                          .order_by(Interview.scheduled_at.desc()).limit(10000)).all()
        return to_csv(['When (UTC)', 'Status', 'Candidate response', 'Job', 'Candidate', 'Email'],
                      [[r[0].isoformat() if r[0] else '', r[1], r[2], r[3], r[4], r[5]] for r in rows]), len(rows)
    raise ValueError('Unknown export')
