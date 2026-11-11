"""Automated auth and RBAC tests; SQLite and stub Redis, no external service required."""
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.models.schema import Base, User, Organization, OrganizationMembership
from app.security.passwords import hash_password, verify_password
from app.security.dependencies import get_db, get_redis


class FakeRedis:
    def __init__(self): self.store = {}
    def get(self, key): return self.store.get(key)
    def setex(self, key, ttl, value): self.store[key] = value
    def delete(self, key): self.store.pop(key, None)
    def incr(self, key):
        num = int(self.store.get(key, 0)) + 1
        self.store[key] = num
        return num
    def expire(self, key, ttl): return True


@pytest.fixture
def setup_app():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    cache = FakeRedis()
    with Session(engine) as db:
        org1 = Organization(name="Instant Mechanic", slug="im")
        org2 = Organization(name="Other Org", slug="other")
        admin = User(email="admin@example.test", full_name="Admin", password_hash=hash_password("good-password-123"), is_platform_admin=True)
        recruiter = User(email="recruiter@example.test", full_name="Recruiter", password_hash=hash_password("good-password-234"))
        candidate = User(email="candidate@example.test", full_name="Candidate", password_hash=hash_password("good-password-345"))
        db.add_all([org1, org2, admin, recruiter, candidate]); db.flush()
        db.add(OrganizationMembership(user_id=recruiter.id, organization_id=org1.id, role="recruiter"))
        db.commit()
        org1_id, org2_id = org1.id, org2.id
    def session_dep():
        with Session(engine) as db: yield db
    def redis_dep(): yield cache
    app.dependency_overrides[get_db] = session_dep
    app.dependency_overrides[get_redis] = redis_dep
    try:
        with TestClient(app) as client:
            yield client, org1_id, org2_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(client, email="admin@example.test", password="good-password-123"):
    return client.post("/api/auth/login", json={"email": email, "password": password},
                       headers={"origin": "http://127.0.0.1:3000"})


def test_password_hash_and_dummy_verification():
    stored = hash_password("a-strong-password-123")
    assert stored.startswith("$argon2id$")
    assert verify_password(stored, "a-strong-password-123")
    assert not verify_password(stored, "wrong-password")
    assert not verify_password(None, "wrong-password")


def test_login_session_logout_csrf(setup_app):
    client, _, _ = setup_app
    assert client.get("/api/auth/me").status_code == 401
    result = login(client)
    assert result.status_code == 200, result.text
    assert "httponly" in result.headers["set-cookie"].lower()
    assert "good-password" not in result.text
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["is_platform_admin"] is True
    assert client.get("/api/auth/admin-check").status_code == 200
    denied = client.post("/api/auth/logout", json={}, headers={"origin": "http://127.0.0.1:3000"})
    assert denied.status_code == 403
    csrf = me.json()["csrf_token"]
    ok = client.post("/api/auth/logout", json={}, headers={"origin":"http://127.0.0.1:3000", "x-csrf-token":csrf})
    assert ok.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_invalid_password_and_rate_limit(setup_app):
    client, _, _ = setup_app
    for i in range(8):
        assert login(client, password="incorrect").status_code == 401
    assert login(client).status_code == 429


def test_origin_restriction_and_no_privilege_escalation(setup_app):
    client, org1, org2 = setup_app
    assert client.post("/api/auth/login", json={"email":"admin@example.test","password":"good-password-123"}, headers={"origin":"https://evil.example"}).status_code == 403
    result = login(client, "recruiter@example.test", "good-password-234")
    assert result.status_code == 200
    assert client.get("/api/auth/admin-check").status_code == 403
    assert client.get(f"/api/auth/organizations/{org1}/recruiter-check").status_code == 200
    assert client.get(f"/api/auth/organizations/{org2}/recruiter-check").status_code == 403


def test_candidate_cannot_recruit(setup_app):
    client, org1, _ = setup_app
    assert login(client, "candidate@example.test", "good-password-345").status_code == 200
    assert client.get(f"/api/auth/organizations/{org1}/recruiter-check").status_code == 403
