"""Transactional, organization-scoped operations; no blind agent API calls."""
import hashlib
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.schema import Application, CandidateProfile, Interview, Job, User
from .models import AgentProposal, AgentAudit
from .graph import propose
from .policy import validate_draft, KINDS


def utcnow(): return datetime.now(timezone.utc)

def lookup_context(db: Session, organization_id: UUID, target_type: str, target_id: UUID):
    if target_type=='interview':
        interview=db.get(Interview,target_id)
        application=db.get(Application,interview.application_id) if interview else None
    elif target_type=='application':
        application=db.get(Application,target_id)
        interview=None
    else: raise HTTPException(422,'Unsupported target type')
    job=db.get(Job,application.job_id) if application else None
    if not job or job.organization_id!=organization_id: raise HTTPException(404,'Recruitment record not found')
    candidate=db.get(CandidateProfile,application.candidate_id)
    user=db.get(User,candidate.user_id) if candidate else None
    if not user or not user.active: raise HTTPException(404,'Candidate account not found')
    when=interview.scheduled_at.isoformat() if interview and interview.scheduled_at else ''
    return {'user':user,'job':job,'application':application,'interview':interview,'when':when}

def log_event(db, org, actor, event, proposal=None, details=None):
    db.add(AgentAudit(organization_id=org,actor_id=actor,proposal_id=proposal,event=event,details=details or {}))

def create_proposal(db: Session, org: UUID, actor: UUID|None, kind: str, target_type: str, target_id: UUID, key: str|None=None):
    if kind not in KINDS or kind=='task_suggestion':
        raise HTTPException(422,'Unsupported proposal kind')
    ctx=lookup_context(db,org,target_type,target_id)
    if kind=='interview_reminder' and not ctx['interview']:
        raise HTTPException(422,'Interview reminder needs an interview')
    if kind=='task_suggestion': raise HTTPException(422,'Create manual tasks using task endpoint')
    try:
        state=propose({'kind':kind,'candidate_name':ctx['user'].full_name,'job_title':ctx['job'].title,'scheduled':ctx['when']})
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    key=key or hashlib.sha256(f'{kind}:{target_type}:{target_id}:{utcnow().date()}'.encode()).hexdigest()
    existing=db.scalar(select(AgentProposal).where(AgentProposal.organization_id==org,AgentProposal.dedupe_key==key))
    if existing: return existing,False
    row=AgentProposal(organization_id=org,created_by_id=actor,kind=kind,target_type=target_type,target_id=target_id,title=f'{kind.replace("_"," ").title()} - {ctx["job"].title}'[:200],draft=state['draft'],recipient_user_id=ctx['user'].id,dedupe_key=key,state='pending')
    db.add(row)
    try:
        db.flush()
        log_event(db,org,actor,'proposal.created',row.id,{'kind':kind,'target_type':target_type})
        db.commit()
    except IntegrityError:
        db.rollback()
        existing=db.scalar(select(AgentProposal).where(AgentProposal.organization_id==org,AgentProposal.dedupe_key==key))
        if not existing: raise
        return existing,False
    db.refresh(row)
    return row,True

def decide(db: Session, org:UUID, proposal_id:UUID, actor:UUID, decision:str, edited_draft:str|None=None, note:str|None=None):
    if decision not in ('approve','reject','cancel'): raise HTTPException(422,'Invalid decision')
    row=db.scalar(select(AgentProposal).where(AgentProposal.id==proposal_id,AgentProposal.organization_id==org).with_for_update())
    if not row: raise HTTPException(404,'Proposal not found')
    if decision=='cancel':
        if row.state not in ('pending','approved','queued'): raise HTTPException(409,'Cannot cancel processing or completed proposals')
        row.state='cancelled'
    else:
        if row.state!='pending': raise HTTPException(409,'Proposal already reviewed')
        if decision=='approve':
            try:
                if edited_draft is not None: row.draft=validate_draft(row.kind,edited_draft)
                else: validate_draft(row.kind,row.draft)
            except ValueError as exc:
                raise HTTPException(422,str(exc))
            row.state='approved'
        else:row.state='rejected'
    row.reviewed_by_id=actor;row.reviewed_at=utcnow();row.approval_note=(note or '')[:1000]
    log_event(db,org,actor,'proposal.'+decision,row.id)
    db.commit();db.refresh(row)
    return row

def serialize(row):
    return {'id':str(row.id),'organization_id':str(row.organization_id),'kind':row.kind,'title':row.title,'target_type':row.target_type,'target_id':str(row.target_id),'draft':row.draft,'state':row.state,'recipient_user_id':str(row.recipient_user_id) if row.recipient_user_id else None,'created_at':row.created_at.isoformat() if row.created_at else None,'reviewed_at':row.reviewed_at.isoformat() if row.reviewed_at else None,'attempts':row.attempts,'last_error':row.last_error}
