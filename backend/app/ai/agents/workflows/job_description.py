"""Job Description agent: check a job and draft a clearer version. Publishing or changing needs a recruiter.

The agent reads the job and writes a draft. It cannot change the job: only a recruiter's approval
in the review step updates the description, and it never changes requirements or publishes the job.
"""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.phase6_agents.service import log_event
from . import jd_quality
from .models import ACTIVE_STATUSES, WorkflowRun
from .resume_review import WorkflowError, advance
from .tools import RecordNotFound, ToolContext, ToolDenied, call_tool

WORKFLOW = 'job_description'
AGENT = 'job_description'
NEEDS_REVIEW = True


def _tool(ctx: ToolContext, name: str, **kwargs):
    return call_tool(ctx, AGENT, name, **kwargs)


def step_load_job(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    return {'job': _tool(ctx, 'load_job', job_id=UUID(state['job_id']))}


def step_check(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    return {'issues': jd_quality.check(state['job'])}


def step_draft(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    issues = state['issues']
    fixes = sum(1 for i in issues if i['severity'] == jd_quality.FIX)
    summary = (f"{len(issues)} suggestion(s) for \"{state['job']['title'][:150]}\": {fixes} wording issue(s) to fix before publishing, "
               f"{len(issues) - fixes} to make it clearer. The draft below only reorganises the current text; "
               'fill in the [placeholders]. Nothing changes until you approve.')
    return {'draft': jd_quality.draft(state['job'], issues), 'summary': summary}


def step_request_review(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    return {'review_task': _tool(ctx, 'request_review', title=f"Review job description draft: {state['job']['title']} (workflow {str(run.id)[:8]})")}


STEPS = [
    ('load_job', step_load_job),
    ('check_quality', step_check),
    ('draft', step_draft),
    ('request_review', step_request_review),
]


def start(db: Session, organization_id: UUID, actor_id: UUID, job_id: UUID) -> tuple[WorkflowRun, bool]:
    try:
        call_tool(ToolContext(db, organization_id, actor_id), AGENT, 'load_job', job_id=job_id)
    except RecordNotFound as exc:
        db.rollback()
        raise WorkflowError(404, str(exc)) from exc
    except ToolDenied as exc:
        db.commit()
        raise WorkflowError(403, str(exc)) from exc
    for existing in db.scalars(select(WorkflowRun).where(
            WorkflowRun.organization_id == organization_id, WorkflowRun.workflow == WORKFLOW,
            WorkflowRun.status.in_(ACTIVE_STATUSES))).all():
        if (existing.state or {}).get('job_id') == str(job_id):
            db.rollback()
            return existing, False
    run = WorkflowRun(organization_id=organization_id, workflow=WORKFLOW, application_id=None,
                      status='running', state={'job_id': str(job_id)}, started_by_id=actor_id)
    db.add(run)
    db.flush()
    log_event(db, organization_id, actor_id, 'workflow.started', details={'run': str(run.id), 'workflow': WORKFLOW})
    db.commit()
    return advance(db, run, actor_id), True
