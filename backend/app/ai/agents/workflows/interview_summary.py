"""Workflow 3: interview completed -> Interview Summary agent -> review draft -> human decision.

Uses the same checkpointed runner, tool allowlist and safety scan as the Resume Review workflow.
The agent prepares evidence from the candidate's own answers and lists unanswered questions.
It never records the hiring decision: a person does that in Interview Studio.
"""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.phase6_agents.service import log_event
from . import evidence
from .models import ACTIVE_STATUSES, WorkflowRun
from .resume_review import Wait, WorkflowError, advance
from .tools import RecordNotFound, ToolContext, ToolDenied, call_tool

WORKFLOW = 'interview_summary'
AGENT = 'interview_summary'
SHORT_ANSWER_WORDS = 5


def _tool(ctx: ToolContext, name: str, **kwargs):
    return call_tool(ctx, AGENT, name, **kwargs)


def _interview_id(state: dict) -> UUID:
    return UUID(state['interview_id'])


def _answer_sentences(items: list[dict]) -> list[dict]:
    """Each answer becomes sentences tagged with its question number."""
    chunks = [{'position': item['position'] - 1, 'excerpt': item['answer']} for item in items if item.get('answer')]
    return evidence.split_sentences(chunks)


def step_load_context(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    return {'interview': _tool(ctx, 'load_interview', interview_id=_interview_id(state))}


def step_check_completed(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    current = _tool(ctx, 'load_interview', interview_id=_interview_id(state))
    if current['status'] != 'completed':
        raise Wait('waiting_interview',
                   f"The interview is {current['status'].replace('_', ' ')}. Resume this run after the candidate finishes it.")
    items = _tool(ctx, 'load_answers', interview_id=_interview_id(state))
    unanswered = [{'position': i['position'], 'question': i['question'][:300]} for i in items
                  if not i.get('answer') or len(i['answer'].split()) < SHORT_ANSWER_WORDS]
    return {'interview': current, 'questions': len(items), 'unanswered': unanswered}


def step_safety_scan(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    items = _tool(ctx, 'load_answers', interview_id=_interview_id(state))
    _, flagged = evidence.safety_scan(_answer_sentences(items))
    return {'flagged': flagged}


def step_build_evidence(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    items = _tool(ctx, 'load_answers', interview_id=_interview_id(state))
    clean, _ = evidence.safety_scan(_answer_sentences(items))
    requirements = _tool(ctx, 'load_requirements', job_id=UUID(state['interview']['job_id']))
    return {'requirements': requirements, 'matrix': evidence.evidence_matrix(requirements, clean)}


def step_summarize(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    return {'summary': evidence.summary(state['interview']['job_title'], state['matrix'], state.get('flagged', []),
                                        source='interview', unanswered=state.get('unanswered', []))}


def step_request_review(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    title = (f"Review interview summary and record your decision in Interview Studio: "
             f"{state['interview']['job_title']} (workflow {str(run.id)[:8]})")
    return {'review_task': _tool(ctx, 'request_review', title=title)}


STEPS = [
    ('load_context', step_load_context),
    ('check_completed', step_check_completed),
    ('safety_scan', step_safety_scan),
    ('build_evidence', step_build_evidence),
    ('summarize', step_summarize),
    ('request_review', step_request_review),
]


def start(db: Session, organization_id: UUID, actor_id: UUID, interview_id: UUID) -> tuple[WorkflowRun, bool]:
    """Start a summary for one interview, or return the open run for it."""
    try:
        info = call_tool(ToolContext(db, organization_id, actor_id), AGENT, 'load_interview', interview_id=interview_id)
    except RecordNotFound as exc:
        db.rollback()
        raise WorkflowError(404, str(exc)) from exc
    except ToolDenied as exc:
        db.commit()  # keep the audit record of the refusal
        raise WorkflowError(403, str(exc)) from exc
    application_id = UUID(info['application_id'])
    for existing in db.scalars(select(WorkflowRun).where(
            WorkflowRun.organization_id == organization_id, WorkflowRun.workflow == WORKFLOW,
            WorkflowRun.application_id == application_id, WorkflowRun.status.in_(ACTIVE_STATUSES))).all():
        if (existing.state or {}).get('interview_id') == str(interview_id):
            db.rollback()
            return existing, False
    run = WorkflowRun(organization_id=organization_id, workflow=WORKFLOW, application_id=application_id,
                      status='running', state={'interview_id': str(interview_id)}, started_by_id=actor_id)
    db.add(run)
    db.flush()
    log_event(db, organization_id, actor_id, 'workflow.started', details={'run': str(run.id), 'workflow': WORKFLOW})
    db.commit()
    return advance(db, run, actor_id), True
