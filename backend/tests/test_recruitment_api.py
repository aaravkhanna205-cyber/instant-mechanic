"""Isolated API regression checks with SQLite + fake Redis; never touches live DB."""
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.models.schema import Base, Organization, User, OrganizationMembership, JobCategory, Job, Application, ApplicationStageHistory
from app.models.categories import seed_official_roles
from app.security.dependencies import get_db, get_redis
from app.security.passwords import hash_password


class FakeRedis:
    def __init__(self): self.store = {}
    def get(self, key): return self.store.get(key)
    def setex(self, key, ttl, value): self.store[key] = value
    def delete(self, key): self.store.pop(key, None)
    def incr(self, key):
        n = int(self.store.get(key, 0)) + 1
        self.store[key] = n
        return n
    def expire(self, key, ttl): return True
    def close(self): pass


@pytest.fixture
def env():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_official_roles(db)
        org1 = Organization(name="Mechanic", slug="mechanic")
        org2 = Organization(name="Elsewhere", slug="elsewhere")
        admin = User(email="admin@example.test", full_name="Admin", password_hash=hash_password("strongpass123!"), is_platform_admin=True)
        recruiter = User(email="recruiter@example.test", full_name="Recruiter", password_hash=hash_password("strongpass123!"))
        candidate = User(email="candidate@example.test", full_name="Candidate", password_hash=hash_password("strongpass123!"))
        db.add_all([org1, org2, admin, recruiter, candidate]); db.flush()
        db.add(OrganizationMembership(user_id=recruiter.id, organization_id=org1.id, role="recruiter"))
        db.commit(); ids = (org1.id, org2.id)
    cache = FakeRedis()
    def db_dep():
        with Session(engine) as s: yield s
    def redis_dep(): yield cache
    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[get_redis] = redis_dep
    try:
        with TestClient(app) as client:
            yield client, ids, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(client, email):
    client.cookies.clear()
    resp = client.post("/api/auth/login", json={"email": email, "password": "strongpass123!"},
                       headers={"origin": "http://127.0.0.1:3000"})
    assert resp.status_code == 200, resp.text
    return {"origin": "http://127.0.0.1:3000", "x-csrf-token": resp.json()["csrf_token"]}


def make_job(client, org_id, headers, status="published"):
    return client.post(f"/api/recruitment/organizations/{org_id}/jobs",
                       json={"title": "Python Developer", "category_slug": "python-tool-developer", "status": status}, headers=headers)


def test_categories_public_and_protected_jobs(env):
    client, (org1, _), _ = env
    assert len(client.get("/api/recruitment/categories").json()) == 11
    assert client.get(f"/api/recruitment/organizations/{org1}/jobs").status_code == 401
    h = login(client, "recruiter@example.test")
    assert make_job(client, org1, h).status_code == 201
    assert len(client.get(f"/api/recruitment/organizations/{org1}/jobs").json()) == 1


def test_cross_org_and_csrf_denied(env):
    client, (org1, org2), _ = env
    h = login(client, "recruiter@example.test")
    assert make_job(client, org2, h).status_code == 403
    assert make_job(client, org1, {"origin": h["origin"]}).status_code == 403
    assert client.get(f"/api/recruitment/organizations/{org2}/candidates").status_code == 403
    job_id = make_job(client, org1, h).json()["id"]
    assert client.patch(f"/api/recruitment/organizations/{org2}/jobs/{job_id}", json={"status":"closed"}, headers=h).status_code == 403
    assert client.patch(f"/api/recruitment/organizations/{org1}/jobs/{job_id}", json={"status":"bogus"}, headers=h).status_code == 422


def test_candidate_applies_only_to_published_and_own_applications(env):
    client, (org1, _), engine = env
    h = login(client, "recruiter@example.test")
    published = make_job(client, org1, h).json()["id"]
    draft = make_job(client, org1, h, status="draft").json()["id"]
    h = login(client, "candidate@example.test")
    assert client.post(f"/api/recruitment/jobs/{draft}/apply", headers=h).status_code == 404
    assert client.post(f"/api/recruitment/jobs/{published}/apply", headers=h).status_code == 201
    assert client.post(f"/api/recruitment/jobs/{published}/apply", headers=h).status_code == 409
    assert len(client.get("/api/recruitment/me/applications").json()) == 1
    with Session(engine) as db:
        assert db.scalar(select(ApplicationStageHistory.new_stage)) == "applied"
    # A candidate cannot read the recruiter's organization-only endpoints.
    assert client.get(f"/api/recruitment/organizations/{org1}/applications").status_code == 403


def test_stage_history_and_interview_workflow(env):
    client, (org1, _), engine = env
    h = login(client, "admin@example.test")
    job_id = make_job(client, org1, h).json()["id"]
    ch = login(client, "candidate@example.test")
    app_id = client.post(f"/api/recruitment/jobs/{job_id}/apply", headers=ch).json()["id"]
    h = login(client, "admin@example.test")
    stage = client.patch(f"/api/recruitment/organizations/{org1}/applications/{app_id}/stage",
                         json={"stage":"trade_test","note":"Practical assessment"}, headers=h)
    assert stage.status_code == 200, stage.text
    assert stage.json()["stage"] == "trade_test"
    scheduled = client.post(f"/api/recruitment/organizations/{org1}/interviews",
                             json={"application_id":app_id,"scheduled_at":"2027-01-01T10:00:00Z"}, headers=h)
    assert scheduled.status_code == 201, scheduled.text
    interview_id = scheduled.json()["id"]
    assert client.patch(f"/api/recruitment/organizations/{org1}/interviews/{interview_id}",
                        json={"status":"completed"}, headers=h).status_code == 200
    assert client.post(f"/api/recruitment/organizations/{org1}/interviews/{interview_id}/feedback",
                       json={"score":5,"comments":"Strong"}, headers=h).status_code == 201
    stats = client.get(f"/api/recruitment/organizations/{org1}/analytics").json()
    assert stats["jobs"] == stats["applications"] == stats["interviews"] == 1
    with Session(engine) as db:
        assert db.scalar(select(Application.stage).where(Application.id == UUID(app_id))) == "trade_test"


def test_admin_only_organization_creation(env):
    client, _, _ = env
    h = login(client, "recruiter@example.test")
    assert client.post("/api/recruitment/organizations", json={"name":"Other", "slug":"other"}, headers=h).status_code == 403
    h = login(client, "admin@example.test")
    assert client.post("/api/recruitment/organizations", json={"name":"Another", "slug":"another"}, headers=h).status_code == 201
    assert client.post("/api/recruitment/organizations", json={"name":"Another", "slug":"another"}, headers=h).status_code == 409
