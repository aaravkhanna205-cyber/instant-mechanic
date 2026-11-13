"""HTTP integration: requires the EXISTING FastAPI security modules, but no live DB/Redis."""
from datetime import datetime,timezone
from uuid import uuid4
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.models.schema import Base,User,Organization,JobCategory,Job,CandidateProfile,Application,Interview
from app.security.dependencies import get_db,require_recruiter_for_org
from app.api.recruitment import require_csrf
from app.phase6_agents.api import router

@pytest.fixture
def api_client():
    engine=create_engine('sqlite+pysqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        org=Organization(name='Authorized Organization',slug='authorized')
        other=Organization(name='Other Org',slug='other')
        recruiter=User(email='recruiter@example.test',full_name='Recruiter',password_hash='test')
        candidate=User(email='candidate@example.test',full_name='Candidate',password_hash='test')
        category=JobCategory(slug='test-role',title='Test Role',department='IT')
        db.add_all([org,other,recruiter,candidate,category]);db.flush()
        cp=CandidateProfile(user_id=candidate.id,skills={})
        job=Job(organization_id=org.id,category_slug=category.slug,title='Developer',description='Test',status='published')
        db.add_all([cp,job]);db.flush()
        application=Application(job_id=job.id,candidate_id=cp.id)
        db.add(application);db.flush()
        interview=Interview(application_id=application.id,status='scheduled',scheduled_at=datetime.now(timezone.utc))
        db.add(interview);db.commit()
        org_id=org.id;other_id=other.id;actor=recruiter;interview_id=interview.id
    app=FastAPI();app.include_router(router)
    def db_dep():
        with Session(engine) as db:yield db
    def auth_dep(organization_id):
        if str(organization_id)!=str(org_id):raise HTTPException(403,'Forbidden')
        return actor
    app.dependency_overrides[get_db]=db_dep
    app.dependency_overrides[require_recruiter_for_org]=auth_dep
    app.dependency_overrides[require_csrf]=lambda:None
    with TestClient(app) as client:
        yield client,org_id,other_id,interview_id
    engine.dispose()

def test_http_approval_lifecycle(api_client):
    client,org,other,interview=api_client
    base=f'/api/phase6/organizations/{org}'
    data={'kind':'interview_reminder','target_type':'interview','target_id':str(interview)}
    resp=client.post(base+'/proposals',json=data)
    assert resp.status_code==201,resp.text
    p=resp.json();assert p['state']=='pending' and p['approval_required']
    assert client.post(base+f"/proposals/{p['id']}/queue").status_code==409
    assert client.post(base+f"/proposals/{p['id']}/decision",json={'decision':'approve'}).status_code==200
    assert client.post(base+f"/proposals/{p['id']}/queue").json()['state']=='queued'
    assert client.get(base+'/overview').json()['total_proposals']==1
    assert client.get(base+'/events').status_code==200
    assert client.get(f'/api/phase6/organizations/{other}/proposals').status_code==403

def test_http_knowledge_and_tasks(api_client):
    client,org,_,_=api_client
    base=f'/api/phase6/organizations/{org}'
    assert client.post(base+'/knowledge',json={'title':'Interview handbook','body':'Recruiters approve interview invitations before sending messages.'}).status_code==201
    assert len(client.get(base+'/knowledge/search',params={'q':'interview approvals'}).json()['citations'])==1
    task=client.post(base+'/tasks',json={'title':'Review applicant documents'})
    assert task.status_code==201,task.text
    task_id=task.json()['id']
    assert client.patch(base+f'/tasks/{task_id}',json={'status':'done'}).status_code==200
    assert client.get(base+'/tasks').json()[0]['status']=='done'

def test_http_blocked_wording_returns_422(api_client):
    client,org,_,interview=api_client
    base=f'/api/phase6/organizations/{org}'
    p=client.post(base+'/proposals',json={'kind':'interview_invitation','target_type':'interview','target_id':str(interview)}).json()
    resp=client.post(base+f"/proposals/{p['id']}/decision",json={'decision':'approve','edited_draft':'Sorry, we must reject your application.'})
    assert resp.status_code==422,resp.text
    assert client.get(base+'/proposals').json()[0]['state']=='pending'
