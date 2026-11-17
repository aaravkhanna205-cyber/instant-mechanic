"""Tool layer for workflow agents.

Every agent may call only the tools on its allowlist.
Every tool re-checks, by itself, that the person who started the workflow may act in this organization
and that the record belongs to this organization. A tool never trusts what the agent passes in.
Every call, allowed or refused, is written to the Phase 6 audit log.
"""
import json
from dataclasses import dataclass
from uuid import UUID
from sqlalchemy import Uuid, bindparam, select, text
from sqlalchemy.orm import Session
from app.models.schema import Application, Interview, Job, JobRequirement, Organization, OrganizationMembership, User
from app.phase6_agents.models import AgentTask
from app.phase6_agents.service import log_event

RECRUITER_ROLES = ('owner', 'admin', 'recruiter')


class ToolDenied(PermissionError):
    """The agent asked for a tool it may not use, or the actor lacks permission."""


class RecordNotFound(LookupError):
    """The record does not exist in this organization. Same message whether missing or foreign."""


@dataclass(frozen=True)
class ToolContext:
    db: Session
    organization_id: UUID
    actor_id: UUID | None
    run_id: UUID | None = None


def ensure_actor(ctx: ToolContext) -> None:
    """Same rule as require_recruiter_for_org, checked again inside every tool."""
    if ctx.actor_id is None:
        raise ToolDenied('A workflow must be started by a signed-in recruiter')
    user = ctx.db.get(User, ctx.actor_id)
    if user is None or not user.active:
        raise ToolDenied('Actor account is not active')
    if user.is_platform_admin:
        return
    org = ctx.db.get(Organization, ctx.organization_id)
    if org is None or not org.active:
        raise ToolDenied('Organization not available')
    roles = ctx.db.scalars(select(OrganizationMembership.role).where(
        OrganizationMembership.user_id == ctx.actor_id,
        OrganizationMembership.organization_id == ctx.organization_id)).all()
    if not any(role in RECRUITER_ROLES for role in roles):
        raise ToolDenied('Actor is not a recruiter in this organization')


def _application_in_org(ctx: ToolContext, application_id: UUID) -> tuple[Application, Job]:
    application = ctx.db.get(Application, application_id)
    job = ctx.db.get(Job, application.job_id) if application else None
    if job is None or job.organization_id != ctx.organization_id:
        raise RecordNotFound('Application not found')
    return application, job


def load_application(ctx: ToolContext, application_id: UUID) -> dict:
    application, job = _application_in_org(ctx, application_id)
    return {'application_id': str(application.id), 'job_id': str(job.id), 'job_title': job.title,
            'candidate_id': str(application.candidate_id), 'stage': application.stage}


def load_requirements(ctx: ToolContext, job_id: UUID) -> list[str]:
    job = ctx.db.get(Job, job_id)
    if job is None or job.organization_id != ctx.organization_id:
        raise RecordNotFound('Job not found')
    rows = ctx.db.scalars(select(JobRequirement).where(JobRequirement.job_id == job.id).order_by(JobRequirement.label)).all()
    return [r.label.strip() for r in rows if r.label and r.label.strip()]


def load_resume(ctx: ToolContext, application_id: UUID) -> dict:
    """Latest consented, processed resume of THIS application's candidate only."""
    application, _ = _application_in_org(ctx, application_id)
    doc = ctx.db.execute(text(
        "SELECT id, status, skills FROM phase4_documents WHERE candidate_id = :cid AND consented = true "
        "ORDER BY created_at DESC LIMIT 1").bindparams(bindparam('cid', type_=Uuid())),
        {'cid': application.candidate_id}).mappings().first()
    if doc is None:
        return {'status': 'no_resume', 'document_id': None, 'skills': [], 'chunks': []}
    if doc['status'] != 'ready':
        return {'status': doc['status'], 'document_id': str(UUID(str(doc['id']))), 'skills': [], 'chunks': []}
    document_id = UUID(str(doc['id']))
    rows = ctx.db.execute(text(
        'SELECT position, excerpt FROM phase4_chunks WHERE document_id = :id ORDER BY position LIMIT 200'
    ).bindparams(bindparam('id', type_=Uuid())), {'id': document_id}).all()
    skills = doc['skills']
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except ValueError:
            skills = []
    if not isinstance(skills, list):
        skills = []
    return {'status': 'ready', 'document_id': str(document_id),
            'skills': [s.get('skill') for s in skills if isinstance(s, dict) and s.get('skill')][:40],
            'chunks': [{'position': r[0], 'excerpt': r[1]} for r in rows]}


def request_review(ctx: ToolContext, title: str) -> dict:
    """Puts a task in the existing Tasks list. It does not message the candidate or change any stage."""
    task = AgentTask(organization_id=ctx.organization_id, title=title[:240], created_by_id=ctx.actor_id, status='open')
    ctx.db.add(task)
    ctx.db.flush()
    return {'task_id': str(task.id)}


def _interview_in_org(ctx: ToolContext, interview_id: UUID) -> tuple[Interview, Application, Job]:
    interview = ctx.db.get(Interview, interview_id)
    if interview is None:
        raise RecordNotFound('Interview not found')
    try:
        application, job = _application_in_org(ctx, interview.application_id)
    except RecordNotFound as exc:
        raise RecordNotFound('Interview not found') from exc
    return interview, application, job


def load_interview(ctx: ToolContext, interview_id: UUID) -> dict:
    interview, application, job = _interview_in_org(ctx, interview_id)
    return {'interview_id': str(interview.id), 'application_id': str(application.id), 'job_id': str(job.id),
            'job_title': job.title, 'status': interview.status, 'stage': application.stage}


def load_answers(ctx: ToolContext, interview_id: UUID) -> list[dict]:
    """Approved questions of THIS interview, each with the candidate's answer (or None)."""
    from app.interview_studio.models import InterviewAnswer, InterviewQuestion
    interview, _, _ = _interview_in_org(ctx, interview_id)
    questions = ctx.db.scalars(select(InterviewQuestion).where(InterviewQuestion.interview_id == interview.id)
                               .order_by(InterviewQuestion.position).limit(100)).all()
    answers = {a.question_id: a.answer for a in ctx.db.scalars(
        select(InterviewAnswer).where(InterviewAnswer.interview_id == interview.id))}
    return [{'position': q.position, 'question': q.text, 'answer': answers.get(q.id)} for q in questions]


TOOLS = {
    'load_application': load_application,
    'load_requirements': load_requirements,
    'load_resume': load_resume,
    'request_review': request_review,
    'load_interview': load_interview,
    'load_answers': load_answers,
}

# The only place that grants tools to agents.
ALLOWLIST: dict[str, frozenset[str]] = {
    'resume_analysis': frozenset({'load_application', 'load_requirements', 'load_resume', 'request_review'}),
    'interview_summary': frozenset({'load_interview', 'load_requirements', 'load_answers', 'request_review'}),
}


def call_tool(ctx: ToolContext, agent: str, name: str, **kwargs):
    details = {'agent': agent, 'tool': name, 'run': str(ctx.run_id) if ctx.run_id else None}
    if name not in ALLOWLIST.get(agent, frozenset()) or name not in TOOLS:
        log_event(ctx.db, ctx.organization_id, ctx.actor_id, 'workflow.tool_denied', details=details)
        raise ToolDenied(f'Agent {agent!r} may not use tool {name!r}')
    try:
        ensure_actor(ctx)
    except ToolDenied:
        log_event(ctx.db, ctx.organization_id, ctx.actor_id, 'workflow.tool_denied', details={**details, 'reason': 'actor'})
        raise
    result = TOOLS[name](ctx, **kwargs)
    log_event(ctx.db, ctx.organization_id, ctx.actor_id, 'workflow.tool', details=details)
    return result
