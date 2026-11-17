"""Phase 6: Job Description agent (draft + human approval) and Recruitment Analytics agent (read-only)."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.models.schema import (Application, ApplicationStageHistory, Base, CandidateProfile, Interview, Job, JobCategory,
                               JobRequirement, Organization, OrganizationMembership, User)
from app.phase6_agents.models import AgentTask
from app.ai.agents.workflows import analytics, jd_quality, job_description, recruitment_analytics, resume_review as flow, tools
from app.ai.agents.workflows.models import WorkflowRun

NOW = datetime.now(timezone.utc)
BIASED_JOB = {
    'title': 'Salesman', 'location': None, 'employment_type': 'full_time',
    'description': 'Young and energetic male only candidates. Must be a rockstar. He will handle walk-in customers.',
    'requirements': [{'label': 'Customer handling', 'required': True}, {'label': 'customer handling', 'required': True},
                     {'label': 'Good attitude', 'required': True}, {'label': 'Two-wheeler licence', 'required': False}],
}


@pytest.fixture
def env():
    engine = create_engine('sqlite+pysqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    org, other = Organization(name='Instant Mechanic', slug='im'), Organization(name='Other', slug='other')
    recruiter = User(email='rec@im.test', full_name='Recruiter', password_hash='x')
    outsider = User(email='out@other.test', full_name='Outsider', password_hash='x')
    db.add_all([org, other, recruiter, outsider, JobCategory(slug='ops', title='Ops', department='Ops')])
    db.flush()
    db.add_all([OrganizationMembership(user_id=recruiter.id, organization_id=org.id, role='recruiter'),
                OrganizationMembership(user_id=outsider.id, organization_id=other.id, role='recruiter')])
    job = Job(organization_id=org.id, category_slug='ops', title='Salesman', description=BIASED_JOB['description'], status='draft')
    support = Job(organization_id=org.id, category_slug='ops', title='Customer Support Executive', description='Support', status='published')
    idle = Job(organization_id=org.id, category_slug='ops', title='Accountant', description='Accounts', status='published')
    foreign = Job(organization_id=other.id, category_slug='ops', title='Foreign job', description='x', status='published')
    db.add_all([job, support, idle, foreign])
    db.flush()
    for req in BIASED_JOB['requirements']:
        db.add(JobRequirement(job_id=job.id, label=req['label'], required=req['required']))
    db.commit()

    def applicant(job_id, days_ago, stage='applied', moved_days_ago=None):
        user = User(email=f'{uuid4().hex[:8]}@cand.test', full_name='Private Name', password_hash='x')
        db.add(user)
        db.flush()
        profile = CandidateProfile(user_id=user.id, skills={})
        db.add(profile)
        db.flush()
        app_ = Application(job_id=job_id, candidate_id=profile.id, stage=stage, applied_at=NOW - timedelta(days=days_ago))
        db.add(app_)
        db.flush()
        if moved_days_ago is not None:
            db.add(ApplicationStageHistory(application_id=app_.id, previous_stage='applied', new_stage=stage,
                                           changed_at=NOW - timedelta(days=moved_days_ago)))
        db.commit()
        return app_

    yield {'db': db, 'engine': engine, 'org': org.id, 'other': other.id, 'recruiter': recruiter.id, 'outsider': outsider.id,
           'job': job.id, 'support': support.id, 'idle': idle.id, 'foreign': foreign.id, 'applicant': applicant}
    db.close()
    engine.dispose()


# ---------------------------------------------------------------- job description: pure checks
def test_checks_find_exclusionary_and_missing_parts():
    issues = jd_quality.check(BIASED_JOB)
    fix = {i['text'].lower() for i in issues if i['severity'] == jd_quality.FIX}
    assert {'salesman', 'young', 'male only'} <= fix
    kinds = {i['kind'] for i in issues}
    assert {'vague', 'gendered', 'short', 'missing_responsibilities', 'missing_hours', 'missing_pay',
            'missing_location', 'duplicate', 'vague_requirement'} <= kinds
    assert issues[0]['severity'] == jd_quality.FIX  # most serious first


def test_draft_reorganises_without_inventing():
    draft = jd_quality.draft(BIASED_JOB, jd_quality.check(BIASED_JOB))
    assert '[Add location]' in draft and '[Add salary range]' in draft and '[Add shift or working hours]' in draft
    assert draft.lower().count('customer handling') == 1  # duplicate removed
    assert 'Nice to have\n- Two-wheeler licence' in draft
    assert '₹' not in draft and 'lpa' not in draft.lower()


def test_clean_job_has_no_fix_issues():
    job = {'title': 'Accountant', 'location': 'Gurugram', 'employment_type': 'full_time',
           'description': 'You will manage day-to-day accounts, GST filing and vendor payments for our service centres. '
                          'Responsibilities include monthly closing in Tally ERP and reports for the finance lead. '
                          'Working hours are 9:30 am to 6:30 pm, Monday to Saturday. Salary: 3.5 to 4.5 LPA. '
                          'We welcome applicants with 2 to 4 years of experience in a services business.',
           'requirements': [{'label': 'Tally ERP', 'required': True}, {'label': 'GST filing', 'required': True}]}
    assert jd_quality.check(job) == []


# ---------------------------------------------------------------- job description: workflow
def test_job_description_needs_approval_to_change_job(env):
    db = env['db']
    run, created = job_description.start(db, env['org'], env['recruiter'], env['job'])
    assert created and run.status == 'waiting_review'
    out = flow.serialize(run)
    assert out['job_title'] == 'Salesman' and out['draft'] and out['issues'] and out['application_id'] is None
    assert db.get(Job, env['job']).description == BIASED_JOB['description']  # agent changed nothing
    again, created = job_description.start(db, env['org'], env['recruiter'], env['job'])
    assert not created and again.id == run.id
    approved = 'Sales executive for our Delhi workshop. You will help walk-in customers choose services.'
    done = flow.review(db, env['org'], run.id, env['recruiter'], 'Removed biased wording', apply_description=approved)
    assert done.status == 'completed' and done.review_decision == 'applied'
    job = db.get(Job, env['job'])
    assert job.description == approved and job.status == 'draft' and job.title == 'Salesman'
    assert len(db.scalars(select(JobRequirement).where(JobRequirement.job_id == job.id)).all()) == 4


def test_job_description_review_without_applying_leaves_job(env):
    db = env['db']
    run, _ = job_description.start(db, env['org'], env['recruiter'], env['job'])
    with pytest.raises(flow.WorkflowError) as short:
        flow.review(db, env['org'], run.id, env['recruiter'], 'Too short', apply_description='tiny')
    assert short.value.status_code == 422
    db.rollback()
    done = flow.review(db, env['org'], run.id, env['recruiter'], 'Will edit later')
    assert done.review_decision == 'accepted' and db.get(Job, env['job']).description == BIASED_JOB['description']


def test_job_description_permissions_and_allowlist(env):
    db = env['db']
    with pytest.raises(flow.WorkflowError) as hidden:
        job_description.start(db, env['org'], env['recruiter'], env['foreign'])
    assert hidden.value.status_code == 404
    with pytest.raises(flow.WorkflowError) as denied:
        job_description.start(db, env['org'], env['outsider'], env['job'])
    assert denied.value.status_code == 403
    ctx = tools.ToolContext(db, env['org'], env['recruiter'])
    for name in ('pipeline_snapshot', 'load_resume', 'load_answers'):
        with pytest.raises(tools.ToolDenied):
            tools.call_tool(ctx, 'job_description', name)
    assert db.scalar(select(WorkflowRun)) is None


def test_only_job_description_runs_can_update_a_job(env, monkeypatch):
    db = env['db']
    env['applicant'](env['support'], 1)
    applied = db.scalar(select(Application))
    monkeypatch.setattr(tools, 'load_resume', lambda ctx, **kw: {'status': 'ready', 'document_id': str(uuid4()), 'skills': [],
                                                                 'chunks': [{'position': 0, 'excerpt': 'Support work.'}]})
    monkeypatch.setitem(tools.TOOLS, 'load_resume', tools.load_resume)
    run, _ = flow.start(db, env['org'], env['recruiter'], applied.id)
    assert run.status == 'waiting_review'
    with pytest.raises(flow.WorkflowError) as wrong:
        flow.review(db, env['org'], run.id, env['recruiter'], 'Try to edit job', apply_description='x' * 40)
    assert wrong.value.status_code == 422


# ---------------------------------------------------------------- analytics
def test_snapshot_and_findings(env):
    a = env['applicant']
    for _ in range(3):
        a(env['support'], 5)                                  # this period, Applied for 5 days: not stuck
    a(env['support'], 40)                                     # previous period
    a(env['support'], 20, stage='screening', moved_days_ago=15)  # stuck in Screening
    a(env['support'], 25, stage='hired', moved_days_ago=10)      # closed: never stuck
    a(env['foreign'], 2)                                      # other organization: never counted
    db = env['db']
    stuck_app = db.scalar(select(Application).where(Application.stage == 'screening'))
    db.add(Interview(application_id=stuck_app.id, status='scheduled', scheduled_at=NOW - timedelta(days=3)))
    db.commit()
    snap = tools.pipeline_snapshot(tools.ToolContext(db, env['org'], env['recruiter']), days=30, now=NOW)
    assert snap['applications_current'] == 5 and snap['applications_previous'] == 1
    assert snap['open_by_stage'] == {'applied': 4, 'screening': 1}   # the 40-day-old one is still open
    assert snap['stuck_by_stage'] == {'applied': 1, 'screening': 1}
    assert snap['interviews_overdue'] == 1
    assert 'Foreign job' not in [j['title'] for j in snap['jobs']]
    texts = ' '.join(f['text'] for f in analytics.findings(snap))
    assert 'waited more than 7 days in Screening' in texts and '1 application(s) have waited more than 7 days in Applied' in texts
    assert 'past their scheduled time' in texts
    assert 'Accountant' in texts and 'no applications' in texts       # published, idle
    assert 'Salesman' not in texts                                    # draft jobs are not flagged
    assert 'Applications in the last 30 days: 5, against 1' in texts


def test_analytics_run_is_read_only_and_completes(env):
    db = env['db']
    env['applicant'](env['support'], 3)
    run, _ = recruitment_analytics.start(db, env['org'], env['recruiter'], 30)
    assert run.status == 'completed' and run.completed_at is not None
    out = flow.serialize(run)
    assert out['findings'] and 'Recruitment report' in out['summary'] and out['job_title'].startswith('Recruitment report')
    assert 'Private Name' not in str(out)                    # no candidate names anywhere
    assert db.scalar(select(AgentTask)) is None              # nothing to approve
    with pytest.raises(flow.WorkflowError) as bad:
        recruitment_analytics.start(db, env['org'], env['recruiter'], 3)
    assert bad.value.status_code == 422
    with pytest.raises(flow.WorkflowError) as denied:
        recruitment_analytics.start(db, env['org'], env['outsider'], 30)
    assert denied.value.status_code == 403
    ctx = tools.ToolContext(db, env['org'], env['recruiter'])
    with pytest.raises(tools.ToolDenied):
        tools.call_tool(ctx, 'recruitment_analytics', 'request_review', title='x')


# ---------------------------------------------------------------- HTTP
def test_http(env):
    from app.api.recruitment import require_csrf
    from app.security.dependencies import get_db, require_recruiter_for_org
    from app.ai.agents.workflows.api import router
    env['applicant'](env['support'], 2)
    app = FastAPI()
    app.include_router(router)

    def db_dep():
        with Session(env['engine']) as session:
            yield session

    def auth_dep(organization_id):
        if str(organization_id) != str(env['org']):
            raise HTTPException(403, 'Forbidden')
        return env['db'].get(User, env['recruiter'])

    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[require_recruiter_for_org] = auth_dep
    app.dependency_overrides[require_csrf] = lambda: None
    base = f"/api/phase6/organizations/{env['org']}/workflows"
    with TestClient(app) as client:
        jobs = {j['title']: j for j in client.get(base + '/jobs').json()}
        assert set(jobs) == {'Accountant', 'Customer Support Executive', 'Salesman'}
        assert jobs['Customer Support Executive']['applications'] == 1
        started = client.post(base + '/job-description', json={'job_id': jobs['Salesman']['id']})
        assert started.status_code == 201, started.text
        run = started.json()
        assert run['workflow'] == 'job_description' and run['status'] == 'waiting_review'
        applied = client.post(base + f"/{run['id']}/review", json={'note': 'Approved', 'apply_description': run['draft']})
        assert applied.status_code == 200 and applied.json()['review_decision'] == 'applied'
        report = client.post(base + '/analytics', json={'days': 30})
        assert report.status_code == 201 and report.json()['status'] == 'completed'
        assert client.post(base + '/analytics', json={'days': 2}).status_code == 422
        assert client.post(base + '/job-description', json={'job_id': str(env['foreign'])}).status_code == 404
