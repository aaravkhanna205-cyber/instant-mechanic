"""Authenticated, CSRF-protected, organization-scoped Phase 6 API."""
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.schema import User, Organization
from app.security.dependencies import get_db, require_recruiter_for_org
from app.api.recruitment import require_csrf
from .models import AgentProposal, AgentAudit, AgentTask, AgentKnowledge, AgentDelivery
from .service import create_proposal, decide, serialize, log_event
from .policy import KINDS, keyword_evidence

router=APIRouter(prefix='/api/phase6/organizations/{organization_id}',tags=['Phase 6 Automation'])

class ProposalCreate(BaseModel):
    kind: str
    target_type: str
    target_id: UUID
class Decision(BaseModel):
    decision: str
    edited_draft: str|None = Field(default=None,max_length=4000)
    note: str|None = Field(default=None,max_length=1000)
class TaskCreate(BaseModel):
    title: str=Field(min_length=4,max_length=240)
    due_at: datetime|None=None
    owner_id: UUID|None=None
class TaskPatch(BaseModel):
    status: str
class KnowledgeCreate(BaseModel):
    title: str=Field(min_length=3,max_length=180)
    body: str=Field(min_length=20,max_length=20000)

@router.post('/proposals',status_code=201)
def new_proposal(organization_id:UUID,payload:ProposalCreate,_:None=Depends(require_csrf),user:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    row,created=create_proposal(db,organization_id,user.id,payload.kind,payload.target_type,payload.target_id)
    return {**serialize(row),'newly_created':created,'approval_required':True}

@router.get('/proposals')
def proposals(organization_id:UUID,state:str|None=None,limit:int=Query(default=50,ge=1,le=100),_:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    q=select(AgentProposal).where(AgentProposal.organization_id==organization_id)
    if state:q=q.where(AgentProposal.state==state)
    return [serialize(r) for r in db.scalars(q.order_by(AgentProposal.created_at.desc()).limit(limit)).all()]

@router.post('/proposals/{proposal_id}/decision')
def review(organization_id:UUID,proposal_id:UUID,payload:Decision,_:None=Depends(require_csrf),user:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    return serialize(decide(db,organization_id,proposal_id,user.id,payload.decision,payload.edited_draft,payload.note))

@router.post('/proposals/{proposal_id}/queue')
def queue(organization_id:UUID,proposal_id:UUID,_:None=Depends(require_csrf),user:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    row=db.scalar(select(AgentProposal).where(AgentProposal.id==proposal_id,AgentProposal.organization_id==organization_id).with_for_update())
    if not row:raise HTTPException(404,'Proposal not found')
    if row.state!='approved':raise HTTPException(409,'Explicit approval required before queueing')
    row.state='queued';log_event(db,organization_id,user.id,'proposal.queued',row.id);db.commit()
    return {'id':str(row.id),'state':'queued','delivery':'pending'}

@router.get('/overview')
def overview(organization_id:UUID,_:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    counts=dict(db.execute(select(AgentProposal.state,func.count()).where(AgentProposal.organization_id==organization_id).group_by(AgentProposal.state)).all())
    open_tasks=db.scalar(select(func.count()).select_from(AgentTask).where(AgentTask.organization_id==organization_id,AgentTask.status=='open')) or 0
    return {'proposal_counts':counts,'open_tasks':open_tasks,'total_proposals':sum(counts.values()),'disclaimer':'Agent proposals require human approval; no automatic hiring decisions'}

@router.get('/events')
def events(organization_id:UUID,_:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    rows=db.scalars(select(AgentAudit).where(AgentAudit.organization_id==organization_id).order_by(AgentAudit.created_at.desc()).limit(100)).all()
    return [{'id':str(r.id),'event':r.event,'proposal_id':str(r.proposal_id) if r.proposal_id else None,'created_at':r.created_at.isoformat() if r.created_at else None} for r in rows]

@router.get('/deliveries')
def deliveries(organization_id:UUID,_:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    rows=db.scalars(select(AgentDelivery).where(AgentDelivery.organization_id==organization_id).order_by(AgentDelivery.created_at.desc()).limit(100)).all()
    return [{'proposal_id':str(r.proposal_id),'mode':r.mode,'status':r.status,'created_at':r.created_at.isoformat() if r.created_at else None} for r in rows]

@router.post('/tasks',status_code=201)
def new_task(organization_id:UUID,body:TaskCreate,_:None=Depends(require_csrf),user:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    if body.owner_id:
        from app.models.schema import OrganizationMembership
        role=db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id==body.owner_id,OrganizationMembership.organization_id==organization_id))
        if not role and not db.scalar(select(User.is_platform_admin).where(User.id==body.owner_id)):
            raise HTTPException(422,'Owner must belong to organization')
    row=AgentTask(organization_id=organization_id,title=body.title,created_by_id=user.id,owner_id=body.owner_id,due_at=body.due_at,status='open')
    db.add(row);db.flush();log_event(db,organization_id,user.id,'task.created',details={'task':str(row.id)});db.commit()
    return {'id':str(row.id),'title':row.title,'status':row.status}

@router.get('/tasks')
def tasks(organization_id:UUID,_:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    rows=db.scalars(select(AgentTask).where(AgentTask.organization_id==organization_id).order_by(AgentTask.created_at.desc()).limit(100)).all()
    return [{'id':str(t.id),'title':t.title,'status':t.status,'due_at':t.due_at.isoformat() if t.due_at else None} for t in rows]

@router.patch('/tasks/{task_id}')
def patch_task(organization_id:UUID,task_id:UUID,body:TaskPatch,_:None=Depends(require_csrf),user:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    if body.status not in ('open','done','cancelled'):raise HTTPException(422,'Invalid task state')
    row=db.scalar(select(AgentTask).where(AgentTask.id==task_id,AgentTask.organization_id==organization_id).with_for_update())
    if not row:raise HTTPException(404,'Task not found')
    row.status=body.status;log_event(db,organization_id,user.id,'task.updated',details={'task':str(row.id),'status':body.status});db.commit()
    return {'id':str(row.id),'status':row.status}

@router.post('/knowledge',status_code=201)
def add_knowledge(organization_id:UUID,body:KnowledgeCreate,_:None=Depends(require_csrf),user:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    row=AgentKnowledge(organization_id=organization_id,title=body.title,body=body.body,created_by_id=user.id)
    db.add(row);db.flush();log_event(db,organization_id,user.id,'knowledge.created',details={'document':str(row.id)});db.commit()
    return {'id':str(row.id),'title':row.title}

@router.get('/knowledge/search')
def search(organization_id:UUID,q:str=Query(min_length=3,max_length=200),_:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    rows=db.scalars(select(AgentKnowledge).where(AgentKnowledge.organization_id==organization_id,AgentKnowledge.active.is_(True)).limit(300)).all()
    hits=keyword_evidence(q,[{'id':x.id,'title':x.title,'body':x.body} for x in rows]);return {'query':q,'citations':hits,'answer':'Only the cited extracts are shown; verify against the source documents.'}

@router.post('/proposals/{proposal_id}/retry')
def retry_failed(organization_id:UUID,proposal_id:UUID,_:None=Depends(require_csrf),user:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    """Explicit human decision to retry after unknown SMTP outcome."""
    row=db.scalar(select(AgentProposal).where(AgentProposal.id==proposal_id,AgentProposal.organization_id==organization_id).with_for_update())
    if not row:raise HTTPException(404,'Proposal not found')
    if row.state!='failed' or row.reviewed_by_id is None:raise HTTPException(409,'Only failed approved actions can be retried')
    if row.attempts>=5:raise HTTPException(409,'Maximum attempts reached; create a new reviewed proposal')
    row.state='queued';row.next_attempt_at=None;row.last_error=None
    log_event(db,organization_id,user.id,'delivery.manual_retry',row.id)
    db.commit()
    return {'id':str(row.id),'state':'queued','note':'Manual retry requested. Check the original delivery before retrying.'}

@router.get('/interview-assistant/{interview_id}')
def interview_assistant(organization_id:UUID,interview_id:UUID,_:User=Depends(require_recruiter_for_org),db:Session=Depends(get_db)):
    from app.models.schema import Interview, Application, Job, JobRequirement
    row=db.get(Interview,interview_id)
    app=db.get(Application,row.application_id) if row else None
    job=db.get(Job,app.job_id) if app else None
    if not job or job.organization_id!=organization_id:raise HTTPException(404,'Interview not found')
    requirements=db.scalars(select(JobRequirement).where(JobRequirement.job_id==job.id)).all()
    labels=[r.label for r in requirements][:8]
    questions=[f'Give a specific example of how you demonstrated {label}. What was the result?' for label in labels]
    if not questions:questions=['Describe a relevant project and your individual responsibilities.','How would you approach an unfamiliar issue in this role?']
    return {'interview_id':str(row.id),'job':job.title,'questions':questions,'score_guidance':'Use documented evidence and structured human judgment. No automatic candidate scoring.'}
