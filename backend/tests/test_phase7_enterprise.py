"""Phase 7: roles, team management, notifications and emails, search, reports, exports, retention, Super Admin.

The real permission checks run; only "who is signed in" is simulated with an X-Test-User header.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.models.schema import (Application, ApplicationStageHistory, AuditLog, Base, CandidateProfile, Interview, Job,
                               JobCategory, Notification, Organization, OrganizationMembership, User)
from app.models.admin_tables import admin_metadata
from app.security import dependencies as deps
from app.security.roles import FULL_ACCESS, RECRUITING
from app.phase7 import notifications, reports, retention

NOW = datetime.now(timezone.utc)


class FakeRedis:
    def __init__(self):
        self.store = {}

    def ping(self):
        return True

    def exists(self, key):
        return key in self.store

    def scan_iter(self, match=None, count=None):
        return iter(())

    def get(self, key):
        return None

    def delete(self, key):
        self.store.pop(key, None)


@pytest.fixture
def env():
    import os
    url = os.getenv('PHASE7_TEST_DATABASE_URL')  # optional: run the same tests on a throwaway PostgreSQL database
    if url:
        engine = create_engine(url)
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public')
    else:
        engine = create_engine('sqlite+pysqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    admin_metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    org = Organization(name='Instant Mechanic', slug='im')
    other = Organization(name='Other Garage', slug='other')
    people = {key: User(email=f'{key}@test.in', full_name=name, password_hash='x')
              for key, name in [('superadmin', 'Super Admin'), ('neeraj', 'Neeraj'), ('aarav', 'Aarav Khanna'),
                                ('recruiter', 'Ritu Recruiter'), ('interviewer', 'Ivan Interviewer'),
                                ('outsider', 'Other Manager'), ('ravi', 'Ravi Kumar'), ('sita', 'Sita Devi'),
                                ('newbie', 'New Person')]}
    people['superadmin'].is_platform_admin = True
    db.add_all([org, other, *people.values(), JobCategory(slug='ops', title='Ops', department='Ops')])
    db.flush()
    for key, role in [('neeraj', 'hr_manager'), ('aarav', 'hiring_manager'), ('recruiter', 'recruiter'),
                      ('interviewer', 'interviewer')]:
        db.add(OrganizationMembership(user_id=people[key].id, organization_id=org.id, role=role))
    db.add(OrganizationMembership(user_id=people['outsider'].id, organization_id=other.id, role='hr_manager'))
    job = Job(organization_id=org.id, category_slug='ops', title='Customer Support Executive', description='x', status='published')
    job2 = Job(organization_id=org.id, category_slug='ops', title='Accountant', description='x', status='published')
    foreign = Job(organization_id=other.id, category_slug='ops', title='Foreign job', description='x', status='published')
    db.add_all([job, job2, foreign])
    db.commit()
    ids = {k: u.id for k, u in people.items()}
    yield {'db': db, 'engine': engine, 'org': org.id, 'other': other.id, 'job': job.id, 'job2': job2.id,
           'foreign': foreign.id, **ids}
    db.close()
    engine.dispose()


@pytest.fixture
def client(env):
    from app.api.recruitment import require_csrf, router as recruitment_router
    from app.api.privacy import router as privacy_router
    from app.phase7.api import ROUTERS
    app = FastAPI()
    for router in (recruitment_router, privacy_router, *ROUTERS):
        app.include_router(router)
    fake = FakeRedis()

    def db_dep():
        with Session(env['engine']) as session:
            yield session

    def user_dep(request: Request):
        raw = request.headers.get('x-test-user')
        with Session(env['engine'], expire_on_commit=False) as session:
            user = session.get(User, UUID(raw)) if raw else None
        if user is None or not user.active:
            raise HTTPException(401, 'Authentication required')
        return user

    app.dependency_overrides[deps.get_db] = db_dep
    app.dependency_overrides[deps.get_current_user] = user_dep
    app.dependency_overrides[deps.get_redis] = lambda: fake
    app.dependency_overrides[require_csrf] = lambda: None
    from app.api import privacy
    app.dependency_overrides[privacy.csrf] = lambda: None
    with TestClient(app) as c:
        def as_(key):
            c.headers['x-test-user'] = str(env[key])
            return c
        c.as_ = as_
        yield c


def org_path(env, suffix='', org='org'):
    return f"/api/phase7/organizations/{env[org]}{suffix}"


def add_application(env, user_key, job_key='job', stage='applied', days_ago=1, history=()):
    db = env['db']
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == env[user_key]))
    if profile is None:
        profile = CandidateProfile(user_id=env[user_key], skills={'Excel': True}, phone='9876543210', city='Delhi')
        db.add(profile)
        db.flush()
    app_ = Application(job_id=env[job_key], candidate_id=profile.id, stage=stage, applied_at=NOW - timedelta(days=days_ago))
    db.add(app_)
    db.flush()
    db.add(ApplicationStageHistory(application_id=app_.id, new_stage='applied', changed_at=NOW - timedelta(days=days_ago)))
    for s, d in history:
        db.add(ApplicationStageHistory(application_id=app_.id, previous_stage='applied', new_stage=s,
                                       changed_by_id=env['aarav'], changed_at=NOW - timedelta(days=d)))
    db.commit()
    return app_


# ------------------------------------------------------------------ roles
def test_role_groups():
    assert {'hr_manager', 'hiring_manager'} <= set(FULL_ACCESS)
    assert 'recruiter' in RECRUITING and 'recruiter' not in FULL_ACCESS
    assert 'interviewer' not in RECRUITING


def test_hr_and_hiring_manager_can_recruit_and_manage(env, client):
    for key in ('neeraj', 'aarav'):
        assert client.as_(key).get(f"/api/recruitment/organizations/{env['org']}/applications").status_code == 200
        assert client.as_(key).get(org_path(env, '/team')).status_code == 200
        assert client.as_(key).get(org_path(env, '/reports/summary')).status_code == 200
    # recruiter recruits but cannot manage the team or export personal data
    assert client.as_('recruiter').get(org_path(env, '/reports/summary')).status_code == 200
    assert client.as_('recruiter').get(org_path(env, '/team')).status_code == 403
    assert client.as_('recruiter').get(org_path(env, '/exports/applications.csv')).status_code == 403
    # interviewer and candidates get nothing here
    assert client.as_('interviewer').get(org_path(env, '/reports/summary')).status_code == 403
    assert client.as_('ravi').get(org_path(env, '/applications/search')).status_code == 403
    # another company's HR manager sees nothing of this company
    assert client.as_('outsider').get(org_path(env, '/team')).status_code == 403
    assert client.as_('outsider').get(org_path(env, '/exports/candidates.csv')).status_code == 403
    assert client.as_('superadmin').get(org_path(env, '/team')).status_code == 200


def test_roles_list(env, client):
    roles = {r['role']: r for r in client.as_('ravi').get('/api/phase7/roles').json()}
    assert roles['hr_manager']['full_access'] and roles['hiring_manager']['full_access']
    assert not roles['candidate']['team_role']


# ------------------------------------------------------------------ team
def test_team_add_change_remove(env, client):
    c = client.as_('neeraj')
    members = {m['email']: m for m in c.get(org_path(env, '/team')).json()['members']}
    assert members['aarav@test.in']['role'] == 'hiring_manager' and members['neeraj@test.in']['full_access']
    added = c.post(org_path(env, '/team'), json={'email': 'NEWBIE@test.in', 'role': 'recruiter'})
    assert added.status_code == 201, added.text
    assert c.post(org_path(env, '/team'), json={'email': 'newbie@test.in', 'role': 'recruiter'}).status_code == 409
    assert c.post(org_path(env, '/team'), json={'email': 'nobody@test.in', 'role': 'recruiter'}).status_code == 404
    assert c.post(org_path(env, '/team'), json={'email': 'sita@test.in', 'role': 'candidate'}).status_code == 422
    assert c.post(org_path(env, '/team'), json={'email': 'sita@test.in', 'role': 'owner'}).status_code == 403
    changed = c.patch(org_path(env, f"/team/{env['newbie']}"), json={'role': 'interviewer'})
    assert changed.status_code == 200 and changed.json()['role'] == 'interviewer'
    assert c.delete(org_path(env, f"/team/{env['newbie']}")).status_code == 200
    db = env['db']
    assert db.scalar(select(Notification).where(Notification.user_id == env['newbie'], Notification.kind == 'team_added'))
    actions = {a.action for a in db.scalars(select(AuditLog)).all()}
    assert {'team.add', 'team.role_change', 'team.remove'} <= actions


def test_team_safety_rules(env, client):
    assert client.as_('neeraj').patch(org_path(env, f"/team/{env['neeraj']}"), json={'role': 'recruiter'}).status_code == 403  # own role
    # Neeraj demotes Aarav: allowed while Neeraj keeps full access
    assert client.as_('neeraj').patch(org_path(env, f"/team/{env['aarav']}"), json={'role': 'recruiter'}).status_code == 200
    # Aarav (now recruiter) cannot manage the team any more
    assert client.as_('aarav').get(org_path(env, '/team')).status_code == 403
    # The Super Admin cannot remove the last full-access person either
    blocked = client.as_('superadmin').patch(org_path(env, f"/team/{env['neeraj']}"), json={'role': 'recruiter'})
    assert blocked.status_code == 409 and 'last person' in blocked.json()['detail']
    assert client.as_('superadmin').delete(org_path(env, f"/team/{env['neeraj']}")).status_code == 409
    assert client.as_('superadmin').patch(org_path(env, f"/team/{env['aarav']}"), json={'role': 'hiring_manager'}).status_code == 200


# ------------------------------------------------------------------ notifications and emails
def test_apply_stage_and_interview_notify_and_queue_emails(env, client):
    db = env['db']
    applied = client.as_('ravi').post(f"/api/recruitment/jobs/{env['job']}/apply")
    assert applied.status_code == 201, applied.text
    app_id = applied.json()['id']
    mine = client.as_('ravi').get('/api/notifications').json()
    assert mine[0]['kind'] == 'application_received' and mine[0]['email_status'] == 'pending'
    team_kinds = {n.kind for n in db.scalars(select(Notification).where(Notification.user_id == env['neeraj'])).all()}
    assert 'new_application' in team_kinds
    assert not db.scalar(select(Notification).where(Notification.user_id == env['interviewer']))  # not a recruiter
    assert not db.scalar(select(Notification).where(Notification.user_id == env['outsider']))      # other company
    moved = client.as_('aarav').patch(f"/api/recruitment/organizations/{env['org']}/applications/{app_id}/stage",
                                      json={'stage': 'shortlisted'})
    assert moved.status_code == 200, moved.text
    when = (NOW + timedelta(days=2)).isoformat()
    scheduled = client.as_('aarav').post(f"/api/recruitment/organizations/{env['org']}/interviews",
                                         json={'application_id': app_id, 'scheduled_at': when})
    assert scheduled.status_code == 201, scheduled.text
    kinds = [n['kind'] for n in client.as_('ravi').get('/api/notifications').json()]
    assert kinds[:2] == ['interview_scheduled', 'stage_shortlisted']
    texts = ' '.join(n['message'] for n in client.as_('ravi').get('/api/notifications').json())
    assert 'shortlisted for Customer Support Executive' in texts and 'Asia/Kolkata' in texts
    assert client.as_('ravi').get('/api/notifications/unread-count').json()['unread'] == 3
    first = client.as_('ravi').get('/api/notifications').json()[0]['id']
    assert client.as_('ravi').post(f'/api/notifications/{first}/read').json()['read'] is True
    assert client.as_('sita').post(f'/api/notifications/{first}/read').status_code == 404  # someone else's
    assert client.as_('ravi').post('/api/notifications/read-all').json()['updated'] == 2
    # Worker sends the three candidate emails (outbox mode stores only)
    sent = []
    count = notifications.send_pending_emails(db, 'outbox', lambda to, subject, body, mode: (sent.append((to, body)) or ('outbox', None)),
                                              site_url='https://example.ts.net')
    assert count == 3 and all(to == 'ravi@test.in' for to, _ in sent)
    assert 'https://example.ts.net/portal/applications' in sent[0][1]
    log = client.as_('neeraj').get(org_path(env, '/emails')).json()
    assert len(log) == 3 and {e['email_status'] for e in log} == {'outbox'} and log[0]['to_email'] == 'ravi@test.in'
    assert client.as_('recruiter').get(org_path(env, '/emails')).status_code == 403


def test_email_failure_is_recorded(env):
    db = env['db']
    notifications.notify(db, env['ravi'], 'x', 'Hello', organization_id=env['org'], email=True)
    db.commit()

    def broken(*args):
        raise ConnectionError('smtp down')

    notifications.send_pending_emails(db, 'smtp', broken)
    row = db.scalar(select(Notification))
    assert row.email_status == 'failed' and 'smtp down' in row.email_error


def test_deletion_request_notifies_super_admin(env, client):
    assert client.as_('ravi').post('/api/privacy/deletion-requests', json={'reason': 'moving away'}).status_code == 201
    row = env['db'].scalar(select(Notification).where(Notification.user_id == env['superadmin']))
    assert row.kind == 'deletion_request' and 'Ravi Kumar' in row.message


# ------------------------------------------------------------------ search, reports, exports
def test_search_filters_and_pages(env, client):
    for i in range(7):
        user = User(email=f'c{i}@test.in', full_name=f'Candidate {i}', password_hash='x')
        env['db'].add(user)
        env['db'].flush()
        env[f'c{i}'] = user.id
        add_application(env, f'c{i}', 'job' if i % 2 else 'job2', stage='screening' if i < 3 else 'applied', days_ago=i)
    add_application(env, 'ravi', 'foreign')  # other company: never shown
    c = client.as_('recruiter')
    page = c.get(org_path(env, '/applications/search?page_size=5')).json()
    assert page['total'] == 7 and page['pages'] == 2 and len(page['items']) == 5
    assert len(c.get(org_path(env, '/applications/search?page=2&page_size=5')).json()['items']) == 2
    assert c.get(org_path(env, '/applications/search?stage=screening')).json()['total'] == 3
    assert c.get(org_path(env, '/applications/search?q=candidate 4')).json()['total'] == 1
    assert c.get(org_path(env, f"/applications/search?job_id={env['job2']}")).json()['total'] == 4
    assert c.get(org_path(env, '/applications/search?q=delhi')).json()['total'] == 7


def test_report_numbers(env, client):
    add_application(env, 'ravi', stage='hired', days_ago=20, history=[('screening', 18), ('interview', 15), ('offer', 12), ('hired', 10)])
    add_application(env, 'sita', stage='rejected', days_ago=8, history=[('screening', 7), ('rejected', 6)])
    add_application(env, 'newbie', 'job2', stage='interview', days_ago=3, history=[('interview', 2)])
    add_application(env, 'ravi', 'job2', days_ago=60)  # before the 30-day period
    db = env['db']
    first = db.scalar(select(Application).where(Application.stage == 'interview'))
    db.add_all([Interview(application_id=first.id, status='completed', scheduled_at=NOW - timedelta(days=2)),
                Interview(application_id=first.id, status='no_show', scheduled_at=NOW - timedelta(days=1)),
                Interview(application_id=first.id, status='scheduled', scheduled_at=NOW + timedelta(days=1))])
    db.commit()
    r = client.as_('neeraj').get(org_path(env, '/reports/summary?days=30')).json()
    assert r['applications'] == 3
    funnel = {f['stage']: f['count'] for f in r['funnel']}
    assert funnel['applied'] == 3 and funnel['screening'] == 2 and funnel['interview'] == 2 and funnel['offer'] == 1 and funnel['hired'] == 1
    assert r['conversion']['applied_to_interview'] == 66.7 and r['conversion']['offer_to_hired'] == 100.0
    assert r['time_to_hire']['hires'] == 1 and r['time_to_hire']['average_days'] == 10.0
    assert r['interviews']['due'] == 2 and r['interviews']['completion_rate'] == 50.0
    jobs = {j['title']: j for j in r['jobs']}
    assert jobs['Customer Support Executive']['hired'] == 1 and jobs['Accountant']['interviewed'] == 1
    assert r['activity'][0]['name'] == 'Aarav Khanna'
    assert 'Foreign job' not in jobs


def test_csv_exports_are_safe_and_scoped(env, client):
    db = env['db']
    evil = User(email='evil@test.in', full_name='=HYPERLINK("http://bad")', password_hash='x')
    db.add(evil)
    db.flush()
    env['evil'] = evil.id
    add_application(env, 'evil')
    add_application(env, 'sita', 'foreign')
    res = client.as_('neeraj').get(org_path(env, '/exports/applications.csv'))
    assert res.status_code == 200 and res.headers['content-type'].startswith('text/csv')
    assert 'attachment; filename="instant-mechanic-applications-' in res.headers['content-disposition']
    body = res.content.decode('utf-8-sig')
    assert "'=HYPERLINK" in body and 'Sita' not in body and body.splitlines()[0].startswith('Candidate,Email')
    for kind in ('candidates', 'interviews'):
        assert client.as_('aarav').get(org_path(env, f'/exports/{kind}.csv')).status_code == 200
    assert client.as_('neeraj').get(org_path(env, '/exports/salaries.csv')).status_code == 404
    assert db.scalar(select(AuditLog).where(AuditLog.action == 'export.csv'))


# ------------------------------------------------------------------ Super Admin
def test_platform_admin_toggle_rules(env, client):
    assert client.as_('superadmin').post(f"/api/phase7/admin/users/{env['superadmin']}/platform-admin", json={'value': False}).status_code == 403
    assert client.as_('superadmin').post(f"/api/phase7/admin/users/{env['neeraj']}/platform-admin", json={'value': True}).json()['is_platform_admin']
    assert client.as_('neeraj').post(f"/api/phase7/admin/users/{env['superadmin']}/platform-admin", json={'value': False}).status_code == 200
    # Now Neeraj is the only Super Admin and cannot be removed by anyone
    assert client.as_('aarav').post(f"/api/phase7/admin/users/{env['neeraj']}/platform-admin", json={'value': False}).status_code == 403
    assert client.as_('neeraj').get('/api/phase7/admin/health').json()['database'] is True


def test_retention_preview_and_apply(env, client):
    add_application(env, 'ravi', stage='rejected', days_ago=500, history=[('rejected', 480)])   # eligible
    add_application(env, 'sita', stage='rejected', days_ago=500, history=[('rejected', 30)])    # recent activity
    add_application(env, 'newbie', stage='screening', days_ago=600)                              # still open
    assert client.as_('neeraj').get('/api/phase7/admin/retention').status_code == 403
    preview = client.as_('superadmin').get('/api/phase7/admin/retention?days=365')
    assert preview.status_code == 200, preview.text
    preview = preview.json()
    assert preview['count'] == 1 and preview['candidates'][0]['email'] == 'ravi@test.in'
    assert client.as_('superadmin').get('/api/phase7/admin/retention?days=30').status_code == 422
    assert client.as_('superadmin').post('/api/phase7/admin/retention/apply', json={'days': 365, 'expected_count': 2}).status_code == 409
    done = client.as_('superadmin').post('/api/phase7/admin/retention/apply', json={'days': 365, 'expected_count': 1})
    assert done.status_code == 200 and done.json()['erased'] == 1
    db = env['db']
    db.expire_all()
    ravi = db.get(User, env['ravi'])
    assert ravi.full_name == 'Deleted account' and not ravi.active
    assert db.get(User, env['sita']).active
    assert client.as_('superadmin').get('/api/phase7/admin/retention?days=365').json()['count'] == 0



def test_eligible_skips_staff(env):
    add_application(env, 'recruiter', stage='rejected', days_ago=900)
    assert retention.eligible(env['db'], 365) == []
