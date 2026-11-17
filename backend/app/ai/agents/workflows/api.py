"""Authenticated, CSRF-protected, organization-scoped API for Phase 6 workflows."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.recruitment import require_csrf
from app.models.schema import Application, CandidateProfile, Interview, Job, User
from app.security.dependencies import get_db, require_recruiter_for_org
from . import interview_summary, job_description, recruitment_analytics, resume_review as flow
from .models import WorkflowRun

router = APIRouter(prefix='/api/phase6/organizations/{organization_id}/workflows', tags=['Phase 6 Workflows'])


class StartRun(BaseModel):
    application_id: UUID


class StartInterviewRun(BaseModel):
    interview_id: UUID


class StartJobRun(BaseModel):
    job_id: UUID


class StartAnalyticsRun(BaseModel):
    days: int = Field(default=30, ge=7, le=180)


class ReviewRun(BaseModel):
    note: str = Field(min_length=4, max_length=2000)
    corrections: dict[str, str] = Field(default_factory=dict)
    # Job description runs only: the approved text to save on the job (the recruiter may have edited the draft).
    apply_description: str | None = Field(default=None, max_length=20000)


def _call(fn, *args):
    try:
        return fn(*args)
    except flow.WorkflowError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.get('/applications')
def applications(organization_id: UUID, _: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    """Recent applications in this organization, so nobody has to copy IDs by hand."""
    rows = db.execute(
        select(Application.id, Application.stage, Application.applied_at, Job.title, User.full_name)
        .join(Job, Job.id == Application.job_id)
        .join(CandidateProfile, CandidateProfile.id == Application.candidate_id)
        .join(User, User.id == CandidateProfile.user_id)
        .where(Job.organization_id == organization_id)
        .order_by(Application.applied_at.desc()).limit(100)).all()
    return [{'id': str(r[0]), 'stage': r[1], 'applied_at': r[2].isoformat() if r[2] else None,
             'job_title': r[3], 'candidate_name': r[4]} for r in rows]


@router.get('/interviews')
def interviews(organization_id: UUID, _: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    """Recent interviews in this organization, completed ones first."""
    rows = db.execute(
        select(Interview.id, Interview.status, Interview.scheduled_at, Job.title, User.full_name)
        .join(Application, Application.id == Interview.application_id)
        .join(Job, Job.id == Application.job_id)
        .join(CandidateProfile, CandidateProfile.id == Application.candidate_id)
        .join(User, User.id == CandidateProfile.user_id)
        .where(Job.organization_id == organization_id)
        .order_by((Interview.status == 'completed').desc(), Interview.scheduled_at.desc()).limit(100)).all()
    return [{'id': str(r[0]), 'status': r[1], 'scheduled_at': r[2].isoformat() if r[2] else None,
             'job_title': r[3], 'candidate_name': r[4]} for r in rows]


@router.get('/jobs')
def jobs(organization_id: UUID, _: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    """Jobs in this organization with their application count."""
    counts = select(Application.job_id, func.count(Application.id).label('n')).group_by(Application.job_id).subquery()
    rows = db.execute(select(Job.id, Job.title, Job.status, func.coalesce(counts.c.n, 0))
                      .outerjoin(counts, counts.c.job_id == Job.id)
                      .where(Job.organization_id == organization_id).order_by(Job.title).limit(200)).all()
    return [{'id': str(r[0]), 'title': r[1], 'status': r[2], 'applications': int(r[3])} for r in rows]


@router.post('/job-description', status_code=201)
def start_job_description(organization_id: UUID, body: StartJobRun, _: None = Depends(require_csrf),
                          user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    run, created = _call(job_description.start, db, organization_id, user.id, body.job_id)
    return {**flow.serialize(run), 'newly_created': created}


@router.post('/analytics', status_code=201)
def start_analytics(organization_id: UUID, body: StartAnalyticsRun, _: None = Depends(require_csrf),
                    user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    run, created = _call(recruitment_analytics.start, db, organization_id, user.id, body.days)
    return {**flow.serialize(run), 'newly_created': created}


@router.post('/interview-summary', status_code=201)
def start_interview_summary(organization_id: UUID, body: StartInterviewRun, _: None = Depends(require_csrf),
                            user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    run, created = _call(interview_summary.start, db, organization_id, user.id, body.interview_id)
    return {**flow.serialize(run), 'newly_created': created}


@router.post('', status_code=201)
def start_run(organization_id: UUID, body: StartRun, _: None = Depends(require_csrf),
              user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    run, created = _call(flow.start, db, organization_id, user.id, body.application_id)
    return {**flow.serialize(run), 'newly_created': created}


@router.get('')
def list_runs(organization_id: UUID, status: str | None = None, limit: int = Query(default=50, ge=1, le=100),
              _: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    query = select(WorkflowRun).where(WorkflowRun.organization_id == organization_id)
    if status:
        query = query.where(WorkflowRun.status == status)
    return [flow.serialize(r) for r in db.scalars(query.order_by(WorkflowRun.created_at.desc()).limit(limit)).all()]


@router.get('/{run_id}')
def get_run(organization_id: UUID, run_id: UUID, _: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    return flow.serialize(_call(flow._get, db, organization_id, run_id))


@router.post('/{run_id}/resume')
def resume_run(organization_id: UUID, run_id: UUID, _: None = Depends(require_csrf),
               user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    return flow.serialize(_call(flow.resume, db, organization_id, run_id, user.id))


@router.post('/{run_id}/review')
def review_run(organization_id: UUID, run_id: UUID, body: ReviewRun, _: None = Depends(require_csrf),
               user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    return flow.serialize(_call(flow.review, db, organization_id, run_id, user.id, body.note, body.corrections,
                                body.apply_description))


@router.post('/{run_id}/cancel')
def cancel_run(organization_id: UUID, run_id: UUID, _: None = Depends(require_csrf),
               user: User = Depends(require_recruiter_for_org), db: Session = Depends(get_db)):
    return flow.serialize(_call(flow.cancel, db, organization_id, run_id, user.id))
