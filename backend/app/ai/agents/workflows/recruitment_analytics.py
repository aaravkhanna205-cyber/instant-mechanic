"""Recruitment Analytics agent: read-only report on where hiring slows down.

It uses one read-only tool that returns counts for this organization. It changes nothing,
so it needs no approval and finishes as 'completed'.
"""
from sqlalchemy.orm import Session
from uuid import UUID
from app.phase6_agents.service import log_event
from . import analytics
from .models import WorkflowRun
from .resume_review import WorkflowError, advance
from .tools import ToolContext, ToolDenied, call_tool

WORKFLOW = 'recruitment_analytics'
AGENT = 'recruitment_analytics'
NEEDS_REVIEW = False


def step_load_pipeline(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    return {'snapshot': call_tool(ctx, AGENT, 'pipeline_snapshot', days=state.get('days', 30))}


def step_find_bottlenecks(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    return {'findings': analytics.findings(state['snapshot'])}


def step_write_report(ctx: ToolContext, run: WorkflowRun, state: dict) -> dict:
    return {'summary': analytics.report(state['snapshot'], state['findings'])}


STEPS = [
    ('load_pipeline', step_load_pipeline),
    ('find_bottlenecks', step_find_bottlenecks),
    ('write_report', step_write_report),
]


def start(db: Session, organization_id: UUID, actor_id: UUID, days: int = 30) -> tuple[WorkflowRun, bool]:
    if not 7 <= days <= 180:
        raise WorkflowError(422, 'Days must be between 7 and 180')
    try:
        from .tools import ensure_actor
        ensure_actor(ToolContext(db, organization_id, actor_id))
    except ToolDenied as exc:
        log_event(db, organization_id, actor_id, 'workflow.tool_denied', details={'agent': AGENT, 'reason': 'actor'})
        db.commit()
        raise WorkflowError(403, str(exc)) from exc
    run = WorkflowRun(organization_id=organization_id, workflow=WORKFLOW, application_id=None,
                      status='running', state={'days': days}, started_by_id=actor_id)
    db.add(run)
    db.flush()
    log_event(db, organization_id, actor_id, 'workflow.started', details={'run': str(run.id), 'workflow': WORKFLOW})
    db.commit()
    return advance(db, run, actor_id), True
