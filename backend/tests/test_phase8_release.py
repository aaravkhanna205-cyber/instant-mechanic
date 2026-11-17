"""Phase 8 release checks: resume rule, security (real login, cookies, CSRF, roles, uploads),
server-error monitoring and the repository secret scan.

These use the real app (app.main) with real sign-in; only the database (SQLite) and Redis (in memory) are stand-ins.
"""
import importlib.util
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.categories import seed_official_roles
from app.models.schema import Base, Organization, OrganizationMembership, User
from app.phase8 import monitoring
from app.security.dependencies import get_db, get_redis
from app.security.passwords import hash_password
from app.api import recruitment

ORIGIN = 'http://127.0.0.1:3000'
PASSWORD = 'strongpass123!'


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.lists = {}

    def get(self, key): return self.store.get(key)
    def setex(self, key, ttl, value): self.store[key] = value
    def delete(self, key): self.store.pop(key, None)
    def exists(self, key): return key in self.store
    def ping(self): return True
    def close(self): pass
    def expire(self, key, ttl): return True
    def scan_iter(self, match=None, count=None): return iter(())

    def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('PHASE4_PRIVATE_DIR', str(tmp_path))
    engine = create_engine('sqlite+pysqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:  # the real table is PostgreSQL-only (jsonb); a small stand-in is enough here
        conn.execute(text('CREATE TABLE phase4_documents (id CHAR(32) PRIMARY KEY, user_id CHAR(32), '
                          'consented BOOLEAN, status TEXT)'))
    with Session(engine) as db:
        seed_official_roles(db)
        org1, org2 = Organization(name='Instant Mechanic', slug='im'), Organization(name='Other Garage', slug='other')
        users = {key: User(email=f'{key}@test.in', full_name=key.title(), password_hash=hash_password(PASSWORD))
                 for key in ('super', 'neeraj', 'aarav', 'outsider', 'candidate')}
        users['super'].is_platform_admin = True
        db.add_all([org1, org2, *users.values()])
        db.flush()
        db.add_all([OrganizationMembership(user_id=users['neeraj'].id, organization_id=org1.id, role='hr_manager'),
                    OrganizationMembership(user_id=users['aarav'].id, organization_id=org1.id, role='hiring_manager'),
                    OrganizationMembership(user_id=users['outsider'].id, organization_id=org2.id, role='hr_manager')])
        db.commit()
        ids = {'org1': org1.id, 'org2': org2.id, **{k: u.id for k, u in users.items()}}
    cache = FakeRedis()

    def db_dep():
        with Session(engine) as s:
            yield s

    def redis_dep():
        yield cache

    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[get_redis] = redis_dep
    previous = app.state.error_session_factory
    app.state.error_session_factory = lambda: sessionmaker(bind=engine)
    try:
        with TestClient(app) as client:
            yield client, ids, engine, cache
    finally:
        app.state.error_session_factory = previous
        app.dependency_overrides.clear()
        engine.dispose()


def login(client, key):
    client.cookies.clear()
    resp = client.post('/api/auth/login', json={'email': f'{key}@test.in', 'password': PASSWORD},
                       headers={'origin': ORIGIN})
    assert resp.status_code == 200, resp.text
    return {'origin': ORIGIN, 'x-csrf-token': resp.json()['csrf_token']}


def published_job(client, ids):
    h = login(client, 'aarav')
    resp = client.post(f"/api/recruitment/organizations/{ids['org1']}/jobs",
                       json={'title': 'Customer Support Executive', 'category_slug': 'python-tool-developer',
                             'status': 'published'}, headers=h)
    assert resp.status_code == 201, resp.text
    return resp.json()['id']


def add_resume(engine, user_id, status):
    with engine.begin() as conn:
        conn.execute(text('INSERT INTO phase4_documents VALUES (:id, :u, 1, :s)'),
                     {'id': uuid4().hex, 'u': user_id.hex, 's': status})


# ------------------------------------------------------------------ resume rule

def test_resume_rule_is_on_by_default(monkeypatch):
    monkeypatch.delenv('REQUIRE_RESUME_TO_APPLY', raising=False)
    assert recruitment.resume_required() is True
    monkeypatch.setenv('REQUIRE_RESUME_TO_APPLY', 'no')
    assert recruitment.resume_required() is False


def test_candidate_must_upload_resume_before_applying(env, monkeypatch):
    client, ids, engine, _ = env
    monkeypatch.setenv('REQUIRE_RESUME_TO_APPLY', 'YES')
    job = published_job(client, ids)
    h = login(client, 'candidate')
    blocked = client.post(f'/api/recruitment/jobs/{job}/apply', headers=h)
    assert blocked.status_code == 422
    assert 'upload your resume' in blocked.json()['detail']
    add_resume(engine, ids['candidate'], 'failed')  # a resume that could not be read does not count
    assert client.post(f'/api/recruitment/jobs/{job}/apply', headers=h).status_code == 422
    add_resume(engine, ids['candidate'], 'queued')  # still being read is fine
    assert client.post(f'/api/recruitment/jobs/{job}/apply', headers=h).status_code == 201


# ------------------------------------------------------------------ roles and organizations

def test_candidate_is_denied_every_staff_page(env):
    client, ids, _, _ = env
    login(client, 'candidate')
    org = ids['org1']
    for path in (f'/api/recruitment/organizations/{org}/candidates', f'/api/recruitment/organizations/{org}/jobs',
                 f'/api/phase7/organizations/{org}/team', f'/api/phase7/organizations/{org}/emails',
                 f'/api/phase7/organizations/{org}/reports/summary', f'/api/phase7/organizations/{org}/exports/candidates.csv',
                 f'/api/phase7/organizations/{org}/applications/search', '/api/phase7/admin/health',
                 '/api/phase7/admin/retention', '/api/auth/admin-check'):
        assert client.get(path).status_code == 403, path


def test_staff_cannot_reach_another_organization(env):
    client, ids, _, _ = env
    login(client, 'neeraj')
    mine, theirs = ids['org1'], ids['org2']
    assert client.get(f'/api/phase7/organizations/{mine}/reports/summary').status_code == 200
    for path in ('/team', '/emails', '/reports/summary', '/exports/candidates.csv', '/applications/search'):
        assert client.get(f'/api/phase7/organizations/{theirs}{path}').status_code == 403, path
    assert client.get('/api/phase7/admin/health').status_code == 403  # HR manager is not Super Admin


def test_signed_out_visitor_gets_401(env):
    client, ids, _, _ = env
    client.cookies.clear()
    assert client.get('/api/auth/me').status_code == 401
    assert client.get(f"/api/phase7/organizations/{ids['org1']}/team").status_code == 401
    assert client.get('/api/notifications').status_code == 401


# ------------------------------------------------------------------ login, cookies, CSRF

def test_login_cookie_flags_and_rate_limit(env, monkeypatch):
    client, _, _, _ = env
    client.cookies.clear()
    resp = client.post('/api/auth/login', json={'email': 'aarav@test.in', 'password': PASSWORD},
                       headers={'origin': ORIGIN})
    cookie = resp.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=lax' in cookie and 'path=/' in cookie
    from app.security import sessions
    monkeypatch.setattr(sessions.settings, 'app_env', 'production')
    assert sessions.cookie_options()['secure'] is True
    for _ in range(8):
        assert client.post('/api/auth/login', json={'email': 'neeraj@test.in', 'password': 'wrong'},
                           headers={'origin': ORIGIN}).status_code == 401
    assert client.post('/api/auth/login', json={'email': 'neeraj@test.in', 'password': PASSWORD},
                       headers={'origin': ORIGIN}).status_code == 429


def test_changes_need_csrf_token_and_our_origin(env):
    client, ids, _, _ = env
    h = login(client, 'neeraj')
    url = f"/api/phase7/organizations/{ids['org1']}/team"
    body = {'email': 'candidate@test.in', 'role': 'recruiter'}
    assert client.post(url, json=body, headers={'origin': ORIGIN}).status_code == 403
    assert client.post(url, json=body, headers={**h, 'x-csrf-token': 'forged'}).status_code == 403
    assert client.post(url, json=body, headers={**h, 'origin': 'https://evil.example'}).status_code == 403
    assert client.post(url, json=body, headers=h).status_code == 201  # the same request with a real token works


# ------------------------------------------------------------------ uploads

@pytest.mark.parametrize('name,data,consent', [
    ('resume.pdf', b'this is not really a pdf', 'true'),            # fake PDF
    ('resume.exe', b'MZ\x90\x00 program', 'true'),                    # wrong type
    ('resume.docx', b'PK\x03\x04 broken zip', 'true'),                # broken Word file
    ('resume.pdf', b'', 'true'),                                      # empty
    ('resume.pdf', b'%PDF-' + b'0' * (8 * 1024 * 1024), 'true'),     # over 8 MB
    ('resume.pdf', b'%PDF-1.4 fine', 'false'),                        # no consent
])
def test_bad_uploads_are_rejected(env, name, data, consent):
    client, _, engine, cache = env
    h = login(client, 'candidate')
    resp = client.post('/api/phase4/resumes', headers=h, data={'consent': consent},
                       files={'file': (name, data, 'application/octet-stream')})
    assert resp.status_code == 422, resp.text
    assert not cache.lists
    with engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM phase4_documents')).scalar() == 0


def test_upload_needs_csrf_token(env):
    client, _, _, _ = env
    login(client, 'candidate')
    resp = client.post('/api/phase4/resumes', headers={'origin': ORIGIN}, data={'consent': 'true'},
                       files={'file': ('resume.pdf', b'%PDF-1.4 fine', 'application/pdf')})
    assert resp.status_code == 403


# ------------------------------------------------------------------ server error monitoring

def test_server_errors_are_recorded_without_ids_or_details():
    engine = create_engine('sqlite+pysqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    small = FastAPI()
    monitoring.install(small, lambda: factory)

    @small.get('/boom/{item}')
    def boom(item: str):
        raise RuntimeError('secret candidate detail')

    @small.get('/ok')
    def ok():
        return {'ok': True}

    with TestClient(small, raise_server_exceptions=False) as c:
        item = str(uuid4())
        resp = c.get(f'/boom/{item}?email=someone@test.in')
        assert resp.status_code == 500
        assert 'secret' not in resp.text
        assert c.get('/ok').status_code == 200
    with Session(engine) as db:
        rows = db.query(monitoring.ServerError).all()
        assert len(rows) == 1
        assert rows[0].path == '/boom/{id}' and rows[0].error_type == 'RuntimeError'
        report = monitoring.summary(db)
    assert report['available'] and report['last_24h'] == 1 and report['top'][0]['count'] == 1


def test_monitor_never_breaks_when_database_is_down():
    small = FastAPI()

    def broken():
        raise RuntimeError('no database')

    monitoring.install(small, broken)

    @small.get('/boom')
    def boom():
        raise ValueError('x')

    with TestClient(small, raise_server_exceptions=False) as c:
        assert c.get('/boom').status_code == 500


def test_health_shows_server_errors(env):
    client, _, _, _ = env
    login(client, 'super')
    data = client.get('/api/phase7/admin/health').json()
    assert data['server_errors']['available'] is True
    assert data['server_errors']['last_24h'] == 0


# ------------------------------------------------------------------ secret scan

def test_repository_has_no_committed_secrets():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('secret_scan', root / 'scripts' / 'secret_scan.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['secret_scan'] = module
    spec.loader.exec_module(module)
    assert module.scan(module.tracked_files()) == []
