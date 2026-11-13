"""Phase 6 smoke tests: policy, LangGraph fallback, DB approval lifecycle, tenant isolation."""
from datetime import datetime,timezone
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.models.schema import Base,User,Organization,OrganizationMembership,CandidateProfile,JobCategory,Job,Application,Interview
from app.phase6_agents.models import AgentProposal,AgentAudit,AgentKnowledge,AgentTask,AgentDelivery
from app.phase6_agents.policy import draft_message,validate_draft,keyword_evidence,safe_recipient
from app.phase6_agents.graph import propose
from app.phase6_agents.service import create_proposal,decide,lookup_context

@pytest.fixture
def fixture_db():
    engine=create_engine('sqlite+pysqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        org=Organization(name='Test',slug='test')
        other=Organization(name='Other',slug='other')
        admin=User(email='recruiter@test.example',full_name='Recruiter',password_hash='unused')
        candidate=User(email='candidate@test.example',full_name='Candidate',password_hash='unused')
        category=JobCategory(slug='developer',title='Developer',department='Engineering')
        db.add_all([org,other,admin,candidate,category]);db.flush()
        cp=CandidateProfile(user_id=candidate.id,skills={})
        job=Job(organization_id=org.id,category_slug=category.slug,title='Tool Developer',description='Build safe APIs',status='published')
        db.add_all([cp,job]);db.flush()
        application=Application(job_id=job.id,candidate_id=cp.id)
        db.add(application);db.flush()
        interview=Interview(application_id=application.id,scheduled_at=datetime.now(timezone.utc),status='scheduled')
        db.add(interview);db.commit()
        yield db,org.id,other.id,admin.id,application.id,interview.id
    engine.dispose()

def test_templates_are_safe():
    for kind in ['interview_reminder','application_followup','interview_invitation','document_request']:
        message=draft_message(kind,'Test Candidate','Tool Developer',when='2026-11-20')
        assert 'Test Candidate' in message
        assert validate_draft(kind,message)==message

def test_sensitive_outcomes_blocked():
    with pytest.raises(ValueError):validate_draft('application_followup','We reject this applicant automatically.')
    with pytest.raises(ValueError):validate_draft('invalid','This is a draft message')

def test_graph_requires_approval():
    state=propose({'kind':'interview_reminder','candidate_name':'Test','job_title':'Mechanic'})
    assert state['stage']=='approval_required'
    assert state['valid'] is True
    assert 'draft' in state
    assert 'sent' not in state

def test_knowledge_is_extract_only():
    docs=[{'id':uuid4(),'title':'Recruiter handbook','body':'A recruiter must approve interview invitations'}]
    hits=keyword_evidence('approve interview',docs)
    assert len(hits)==1
    assert hits[0]['matched_terms']>=1
    assert keyword_evidence('nonexistent gibberish',docs)==[]

def test_email_validation():
    assert safe_recipient('candidate@test.example')
    assert not safe_recipient('candidate\r\nBcc:attacker@example.com')

def test_org_scope_lookup(fixture_db):
    db,org,other,actor,application,interview=fixture_db
    assert lookup_context(db,org,'interview',interview)['job'].title=='Tool Developer'
    with pytest.raises(HTTPException) as error:lookup_context(db,other,'interview',interview)
    assert error.value.status_code==404

def test_create_and_approve(fixture_db):
    db,org,_,actor,_,interview=fixture_db
    p,created=create_proposal(db,org,actor,'interview_reminder','interview',interview)
    assert created and p.state=='pending' and p.reviewed_by_id is None
    again,created=create_proposal(db,org,actor,'interview_reminder','interview',interview)
    assert not created and again.id==p.id
    p=decide(db,org,p.id,actor,'approve')
    assert p.state=='approved' and p.reviewed_at is not None
    assert db.scalar(select(AgentDelivery)) is None
    with pytest.raises(HTTPException) as error:decide(db,org,p.id,actor,'approve')
    assert error.value.status_code==409
    assert db.scalar(select(AgentAudit).where(AgentAudit.event=='proposal.approve')) is not None

def test_reject_cannot_execute(fixture_db):
    db,org,_,actor,application,_=fixture_db
    p,_=create_proposal(db,org,actor,'application_followup','application',application)
    p=decide(db,org,p.id,actor,'reject')
    assert p.state=='rejected'
    with pytest.raises(HTTPException):decide(db,org,p.id,actor,'approve')

def test_cross_org_denied(fixture_db):
    db,org,other,actor,application,_=fixture_db
    p,_=create_proposal(db,org,actor,'application_followup','application',application)
    with pytest.raises(HTTPException) as error:decide(db,other,p.id,actor,'approve')
    assert error.value.status_code==404

def test_worker_delivery_only_after_review(fixture_db):
    from app.phase6_agents.worker import process_one
    db,org,other,actor,app,_=fixture_db
    p,_=create_proposal(db,org,actor,'application_followup','application',app)
    assert process_one(db,'outbox') is False
    p=decide(db,org,p.id,actor,'approve')
    p.state='queued';db.commit()
    assert process_one(db,'outbox') is True
    db.refresh(p)
    assert p.state=='outbox'
    delivery=db.scalar(select(AgentDelivery).where(AgentDelivery.proposal_id==p.id))
    assert delivery.status=='outbox' and delivery.mode=='outbox'
    assert process_one(db,'outbox') is False

def test_invalid_proposal_target(fixture_db):
    db,org,_,actor,_,_=fixture_db
    with pytest.raises(HTTPException):create_proposal(db,org,actor,'interview_reminder','interview',uuid4())

def test_local_llm_disabled_by_default(monkeypatch):
    from app.phase6_agents.local_llm import refine
    monkeypatch.setenv('PHASE6_ENABLE_LOCAL_LLM','NO')
    draft=draft_message('application_followup','Test','Developer')
    assert refine('application_followup',draft)==draft

def test_ordinary_job_titles_are_not_blocked():
    message=draft_message('application_followup','Test Candidate','Fire Safety Technician')
    assert 'Fire Safety Technician' in message

def test_blocked_wording_is_a_clear_422(fixture_db):
    db,org,_,actor,application,_=fixture_db
    p,_=create_proposal(db,org,actor,'application_followup','application',application)
    with pytest.raises(HTTPException) as error:decide(db,org,p.id,actor,'approve','Sorry, we must reject your application.')
    assert error.value.status_code==422
    db.rollback()
    assert db.get(AgentProposal,p.id).state=='pending'

def test_scheduler_skips_bad_records_and_does_not_repeat(fixture_db):
    from datetime import timedelta
    from app.phase6_agents.scheduler import scan
    db,org,_,_,application,interview=fixture_db
    now=datetime.now(timezone.utc)
    db.get(Interview,interview).scheduled_at=now+timedelta(hours=3)
    db.get(Application,application).applied_at=now-timedelta(days=5)
    gone=User(email='gone@test.example',full_name='Gone',password_hash='unused',active=False)
    db.add(gone);db.flush()
    cp=CandidateProfile(user_id=gone.id,skills={});db.add(cp);db.flush()
    job=db.scalar(select(Job))
    db.add(Application(job_id=job.id,candidate_id=cp.id,applied_at=now-timedelta(days=5)));db.commit()
    first=scan(db)
    assert first=={'interview_proposals':1,'followup_proposals':1,'skipped':1}
    second=scan(db)
    assert second['interview_proposals']==0 and second['followup_proposals']==0
    assert len(db.scalars(select(AgentProposal)).all())==2
