"""Workflow 1: new resume -> Resume Analysis agent -> evidence matrix -> recruiter review.

How it stays safe and recoverable:
- Steps run in a fixed order. After each step its result is saved in phase6_workflow_runs (a checkpoint).
  If the process stops, Resume continues after the last saved step; finished steps are not repeated.
- The agent reaches data only through tools on its allowlist (tools.py); each tool re-checks permissions.
- Resume text is data. Lines that look like instructions to an AI are set aside and shown to the recruiter.
- The workflow ends by asking a recruiter to review. It never changes the application stage,
  never messages the candidate and never produces a score or ranking.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.phase6_agents.models import AgentTask
from app.phase6_agents.service import log_event
from . import evidence
from .models import ACTIVE_STATUSES, WorkflowRun
from .tools import RecordNotFound, ToolContext, ToolDenied, call_tool

WORKFLOW = 'resume_review'
AGENT = 'resume_analysis'
MAX_ATTEMPTS = 5
STALE_AFTER = timedelta(minutes=2)


class WorkflowError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class Wait(Exception):
    """A step cannot finish yet (for example, the resume is still processing). Not a failure."""
    def __init__(self, status: str, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _tool(ctx: ToolContext, name: str, **kwargs):
    return call_tool(ctx, AGENT, name, **kwargs)


# ---------------------------------------------------------------- steps
def step_load_context(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    return {'application': _tool(ctx, 'load_application', application_id=run.application_id)}


def step_check_resume(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    resume = _tool(ctx, 'load_resume', application_id=run.application_id)
    if resume['status'] == 'no_resume':
        raise Wait('waiting_resume', 'The candidate has no consented resume yet. Resume this run after one is uploaded.')
    if resume['status'] != 'ready':
        raise Wait('waiting_resume', f"The resume is {resume['status']}. Resume this run once Phase 4 has processed it.")
    return {'resume': {'document_id': resume['document_id'], 'skills': resume['skills'], 'parts': len(resume['chunks'])}}


def _sentences(ctx: ToolContext, run: WorkflowRun) -> list[dict]:
    # The resume text is read again rather than stored in the run, so the run keeps no copy of it.
    resume = _tool(ctx, 'load_resume', application_id=run.application_id)
    if resume['status'] != 'ready':
        raise Wait('waiting_resume', 'The resume is no longer available. Resume this run once one is ready.')
    return evidence.split_sentences(resume['chunks'])


def step_safety_scan(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    _, flagged = evidence.safety_scan(_sentences(ctx, run))
    return {'flagged': flagged}


def step_build_evidence(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    clean, _ = evidence.safety_scan(_sentences(ctx, run))
    requirements = _tool(ctx, 'load_requirements', job_id=UUID(state['application']['job_id']))
    return {'requirements': requirements, 'matrix': evidence.evidence_matrix(requirements, clean)}


def step_summarize(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    return {'summary': evidence.summary(state['application']['job_title'], state['matrix'], state.get('flagged', []))}


def step_request_review(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    title = f"Review resume evidence: {state['application']['job_title']} (workflow {str(run.id)[:8]})"
    return {'review_task': _tool(ctx, 'request_review', title=title)}


STEPS = [
    ('load_context', step_load_context),
    ('check_resume', step_check_resume),
    ('safety_scan', step_safety_scan),
    ('build_evidence', step_build_evidence),
    ('summarize', step_summarize),
    ('request_review', step_request_review),
]
STEP_NAMES = [name for name, _ in STEPS]


def _error_text(exc: Exception) -> str:
    if isinstance(exc, (ToolDenied, RecordNotFound)):
        return str(exc)[:300]
    return f'{type(exc).__name__}: {exc}'[:300]


# ---------------------------------------------------------------- runner
def advance(db: Session, run: WorkflowRun, actor_id: UUID | None) -> WorkflowRun:
    """Run every step after the last checkpoint. Saves after each step."""
    if run.status in ('completed', 'cancelled', 'waiting_review'):
        return run
    run.status = 'running'
    run.last_error = None
    db.commit()
    start = STEP_NAMES.index(run.step) + 1 if run.step else 0
    for name, fn in STEPS[start:]:
        ctx = ToolContext(db=db, organization_id=run.organization_id, actor_id=actor_id, run_id=run.id)
        try:
            updates = fn(ctx, run, dict(run.state or {}))
        except Wait as wait:
            db.rollback()
            run.status = wait.status
            run.state = {**(run.state or {}), 'waiting_reason': wait.reason}
            log_event(db, run.organization_id, actor_id, 'workflow.waiting', details={'run': str(run.id), 'step': name})
            db.commit()
            return run
        except Exception as exc:  # noqa: BLE001 - every failure is recorded on the run, never hidden
            db.rollback()
            run.status = 'failed'
            run.attempts = (run.attempts or 0) + 1
            run.last_error = f'Step {name} failed. {_error_text(exc)}'
            log_event(db, run.organization_id, actor_id, 'workflow.step_failed',
                      details={'run': str(run.id), 'step': name, 'error': _error_text(exc)})
            db.commit()
            return run
        # A new dict is assigned so the JSON column is saved.
        run.state = {**(run.state or {}), **updates, 'waiting_reason': None}
        run.step = name
        log_event(db, run.organization_id, actor_id, 'workflow.step_done', details={'run': str(run.id), 'step': name})
        db.commit()  # checkpoint
    run.status = 'waiting_review'
    log_event(db, run.organization_id, actor_id, 'workflow.review_requested', details={'run': str(run.id)})
    db.commit()
    return run


def _get(db: Session, organization_id: UUID, run_id: UUID, lock: bool = False) -> WorkflowRun:
    query = select(WorkflowRun).where(WorkflowRun.id == run_id, WorkflowRun.organization_id == organization_id)
    run = db.scalar(query.with_for_update() if lock else query)
    if run is None:
        raise WorkflowError(404, 'Workflow run not found')
    return run


def start(db: Session, organization_id: UUID, actor_id: UUID, application_id: UUID) -> tuple[WorkflowRun, bool]:
    """Start a run, or return the one already open for this application."""
    existing = db.scalar(select(WorkflowRun).where(
        WorkflowRun.organization_id == organization_id, WorkflowRun.workflow == WORKFLOW,
        WorkflowRun.application_id == application_id, WorkflowRun.status.in_(ACTIVE_STATUSES)))
    if existing:
        return existing, False
    try:
        # Checks permission and that the application belongs to this organization before anything is saved.
        call_tool(ToolContext(db, organization_id, actor_id), AGENT, 'load_application', application_id=application_id)
    except RecordNotFound as exc:
        db.rollback()
        raise WorkflowError(404, str(exc)) from exc
    except ToolDenied as exc:
        db.commit()  # keep the audit record of the refusal
        raise WorkflowError(403, str(exc)) from exc
    run = WorkflowRun(organization_id=organization_id, workflow=WORKFLOW, application_id=application_id,
                      status='running', state={}, started_by_id=actor_id)
    db.add(run)
    db.flush()
    log_event(db, organization_id, actor_id, 'workflow.started', details={'run': str(run.id), 'workflow': WORKFLOW})
    db.commit()
    return advance(db, run, actor_id), True


def resume(db: Session, organization_id: UUID, run_id: UUID, actor_id: UUID, now: datetime | None = None) -> WorkflowRun:
    """Continue a run that failed, is waiting for a resume, or stopped mid-way (for example after a restart)."""
    run = _get(db, organization_id, run_id, lock=True)
    if run.status in ('completed', 'cancelled', 'waiting_review'):
        raise WorkflowError(409, f'Run is {run.status}; nothing to resume')
    if run.status == 'failed' and (run.attempts or 0) >= MAX_ATTEMPTS:
        raise WorkflowError(409, 'Maximum attempts reached; cancel this run and start a new one')
    if run.status == 'running':
        updated = run.updated_at
        if updated is not None and updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if updated is not None and (now or utcnow()) - updated < STALE_AFTER:
            raise WorkflowError(409, 'Run is still in progress; try again in two minutes')
    log_event(db, organization_id, actor_id, 'workflow.resumed', details={'run': str(run.id), 'after_step': run.step})
    db.commit()
    return advance(db, run, actor_id)


def review(db: Session, organization_id: UUID, run_id: UUID, actor_id: UUID, note: str,
           corrections: dict[str, str] | None = None) -> WorkflowRun:
    """Recruiter confirms or corrects the evidence. The application stage is not touched."""
    run = _get(db, organization_id, run_id, lock=True)
    if run.status != 'waiting_review':
        raise WorkflowError(409, 'Only runs waiting for review can be reviewed')
    note = (note or '').strip()
    if not 4 <= len(note) <= 2000:
        raise WorkflowError(422, 'Review note must be 4-2000 characters')
    corrections = corrections or {}
    matrix = [dict(row) for row in (run.state or {}).get('matrix', [])]
    labels = {row['requirement'] for row in matrix}
    for label, status in corrections.items():
        if label not in labels:
            raise WorkflowError(422, f'Unknown requirement: {label[:80]}')
        if status not in evidence.STATUSES:
            raise WorkflowError(422, f'Status must be one of {", ".join(evidence.STATUSES)}')
    for row in matrix:
        row['recruiter_status'] = corrections.get(row['requirement'], row['status'])
    run.state = {**run.state, 'matrix': matrix}
    run.status = 'completed'
    run.review_decision = 'corrected' if corrections else 'accepted'
    run.review_note = note
    run.reviewed_by_id = actor_id
    run.completed_at = utcnow()
    task_id = (run.state.get('review_task') or {}).get('task_id')
    if task_id:
        task = db.scalar(select(AgentTask).where(AgentTask.id == UUID(task_id), AgentTask.organization_id == organization_id))
        if task and task.status == 'open':
            task.status = 'done'
    log_event(db, organization_id, actor_id, 'workflow.reviewed',
              details={'run': str(run.id), 'decision': run.review_decision, 'corrections': len(corrections)})
    db.commit()
    return run


def cancel(db: Session, organization_id: UUID, run_id: UUID, actor_id: UUID) -> WorkflowRun:
    run = _get(db, organization_id, run_id, lock=True)
    if run.status in ('completed', 'cancelled'):
        raise WorkflowError(409, f'Run is already {run.status}')
    run.status = 'cancelled'
    run.completed_at = utcnow()
    log_event(db, organization_id, actor_id, 'workflow.cancelled', details={'run': str(run.id)})
    db.commit()
    return run


def serialize(run: WorkflowRun) -> dict:
    state = run.state or {}
    application = state.get('application') or {}
    done = STEP_NAMES.index(run.step) + 1 if run.step in STEP_NAMES else 0
    return {
        'id': str(run.id), 'workflow': run.workflow, 'application_id': str(run.application_id),
        'job_title': application.get('job_title'), 'status': run.status, 'attempts': run.attempts,
        'steps': [{'name': name, 'done': i < done} for i, name in enumerate(STEP_NAMES)],
        'waiting_reason': state.get('waiting_reason'), 'last_error': run.last_error,
        'skills_to_verify': (state.get('resume') or {}).get('skills', []),
        'matrix': state.get('matrix', []), 'flagged': state.get('flagged', []), 'summary': state.get('summary'),
        'review_decision': run.review_decision, 'review_note': run.review_note,
        'created_at': run.created_at.isoformat() if run.created_at else None,
        'completed_at': run.completed_at.isoformat() if run.completed_at else None,
        'disclaimer': 'Unverified resume claims. Not a score, ranking or hiring decision; a recruiter decides.',
    }
