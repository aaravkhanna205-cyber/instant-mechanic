"""Candidate import, data-deletion and enriched recruitment API checks.

Isolated: SQLite + a fake Redis. The administration tables come from
``admin_metadata``; PostgreSQL gets them from migrations 0002 and 0003.
"""
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.candidate_import import UNUSABLE_PASSWORD
from app.main import app
from app.models.admin_tables import admin_metadata, data_deletion_requests, import_rows
from app.models.categories import seed_official_roles
from app.models.schema import (
    Application, ApplicationStageHistory, Base, CandidateProfile, Interview, Organization,
    OrganizationMembership, User,
)
from app.security.dependencies import get_db, get_redis
from app.security.passwords import hash_password

ORIGIN = "http://127.0.0.1:3000"
PASSWORD = "strongpass123!"


class FakeRedis:
    def __init__(self): self.store = {}
    def get(self, key): return self.store.get(key)
    def setex(self, key, ttl, value): self.store[key] = value
    def delete(self, key): self.store.pop(key, None)
    def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]
    def expire(self, key, ttl): return True
    def scan_iter(self, match="*", count=100):
        prefix = match.rstrip("*")
        return [key for key in list(self.store) if key.startswith(prefix)]
    def close(self): pass


@pytest.fixture
def env():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    admin_metadata.create_all(engine)
    with Session(engine) as db:
        seed_official_roles(db)
        org1, org2 = Organization(name="Mechanic", slug="mechanic"), Organization(name="Elsewhere", slug="elsewhere")
        people = [
            User(email="admin@example.test", full_name="Admin", password_hash=hash_password(PASSWORD), is_platform_admin=True),
            User(email="recruiter@example.test", full_name="Recruiter", password_hash=hash_password(PASSWORD)),
            User(email="outsider@example.test", full_name="Outsider", password_hash=hash_password(PASSWORD)),
            User(email="candidate@example.test", full_name="Existing Candidate", password_hash=hash_password(PASSWORD)),
        ]
        db.add_all([org1, org2, *people]); db.flush()
        db.add(OrganizationMembership(user_id=people[1].id, organization_id=org1.id, role="recruiter"))
        db.add(OrganizationMembership(user_id=people[2].id, organization_id=org2.id, role="recruiter"))
        db.commit(); ids = (org1.id, org2.id)
    cache = FakeRedis()
    def db_dep():
        with Session(engine) as session: yield session
    def redis_dep(): yield cache
    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[get_redis] = redis_dep
    try:
        with TestClient(app) as client:
            yield client, ids, engine, cache
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(client, email):
    client.cookies.clear()
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}, headers={"origin": ORIGIN})
    assert response.status_code == 200, response.text
    return {"origin": ORIGIN, "x-csrf-token": response.json()["csrf_token"]}


def make_job(client, org, headers, title="Python Developer", status="published"):
    response = client.post(f"/api/recruitment/organizations/{org}/jobs", headers=headers,
                           json={"title": title, "category_slug": "python-tool-developer", "status": status})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def csv_file(text, name="candidates.csv"):
    return {"file": (name, text.encode("utf-8"), "text/csv")}


GOOD = ("full_name,email,phone,city,skills,job_title\n"
        "Asha Verma,asha@example.test,98100,Delhi,\"Python, SQL\",Python Developer\n"
        "Existing Candidate,candidate@example.test,,,,\n")
BASE = "/api/admin-v3/organizations"


def test_candidate_import_preview_is_read_only_and_reports_errors(env):
    client, (org1, _), engine, _ = env
    headers = login(client, "recruiter@example.test")
    job = make_job(client, org1, headers)
    bad = ("full_name,email,job_title\n"
           "A,not-an-email,Python Developer\n"
           "Ravi Kumar,ravi@example.test,No Such Job\n"
           "Ravi Kumar,ravi@example.test,\n")
    preview = client.post(f"{BASE}/{org1}/candidate-imports/preview", files=csv_file(bad))
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["valid_count"] == 0
    assert [e["row"] for e in body["errors"]] == [2, 3, 4]
    assert "no vacancy" in body["errors"][2]["errors"][0]
    ok = client.post(f"{BASE}/{org1}/candidate-imports/preview", files=csv_file(GOOD), data={"job_id": job}).json()
    assert (ok["valid_count"], ok["new_accounts"], ok["existing_accounts"], ok["errors"]) == (2, 1, 1, [])
    with Session(engine) as db:
        assert db.scalar(select(func.count(Application.id))) == 0
        assert db.scalar(select(func.count(User.id))) == 4


def test_candidate_import_commit_requires_csrf_consent_and_clean_rows(env):
    client, (org1, _), engine, _ = env
    headers = login(client, "recruiter@example.test")
    job = make_job(client, org1, headers)
    url = f"{BASE}/{org1}/candidate-imports/commit"
    data = {"job_id": job, "consent_confirmed": "true"}
    assert client.post(url, files=csv_file(GOOD), data=data, headers={"origin": ORIGIN}).status_code == 403
    assert client.post(url, files=csv_file(GOOD), data={"job_id": job}, headers=headers).status_code == 422
    mixed = GOOD + "X,broken,,,,\n"
    rejected = client.post(url, files=csv_file(mixed), data=data, headers=headers)
    assert rejected.status_code == 422 and rejected.json()["detail"]["errors"][0]["row"] == 4
    with Session(engine) as db:
        assert db.scalar(select(func.count(Application.id))) == 0, "a bad row must block the whole file"

    done = client.post(url, files=csv_file(GOOD), data=data, headers=headers)
    assert done.status_code == 201, done.text
    assert (done.json()["created"], done.json()["new_accounts"]) == (2, 1)
    with Session(engine) as db:
        imported = db.scalar(select(User).where(User.email == "asha@example.test"))
        assert imported.password_hash == UNUSABLE_PASSWORD and not imported.is_platform_admin
        profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == imported.id))
        assert (profile.city, profile.skills) == ("Delhi", {"Python": True, "SQL": True})
        assert db.scalar(select(func.count(ApplicationStageHistory.id))) == 2
    # An imported account has no password, so nobody can sign in as that person.
    assert client.post("/api/auth/login", json={"email": "asha@example.test", "password": UNUSABLE_PASSWORD},
                       headers={"origin": ORIGIN}).status_code == 401
    headers = login(client, "recruiter@example.test")
    names = {c["full_name"] for c in client.get(f"/api/recruitment/organizations/{org1}/candidates").json()}
    assert names == {"Asha Verma", "Existing Candidate"}
    again = client.post(url, files=csv_file(GOOD), data=data, headers=headers)
    assert again.status_code == 422 and "already applied" in again.text
    batches = client.get(f"{BASE}/{org1}/imports").json()
    assert [(b["kind"], b["status"]) for b in batches] == [("candidates", "applied")]


def test_candidate_import_is_organization_scoped(env):
    client, (org1, org2), _, _ = env
    headers = login(client, "recruiter@example.test")
    job = make_job(client, org1, headers)
    done = client.post(f"{BASE}/{org1}/candidate-imports/commit", files=csv_file(GOOD),
                       data={"job_id": job, "consent_confirmed": "true"}, headers=headers).json()
    headers = login(client, "outsider@example.test")
    assert client.post(f"{BASE}/{org1}/candidate-imports/preview", files=csv_file(GOOD)).status_code == 403
    # A vacancy from another organization cannot be used as the target.
    assert client.post(f"{BASE}/{org2}/candidate-imports/preview", files=csv_file(GOOD), data={"job_id": job}).status_code == 422
    assert client.post(f"{BASE}/{org2}/candidate-imports/{done['batch_id']}/undo", headers=headers).status_code == 404
    assert client.post(f"{BASE}/{org1}/candidate-imports/{done['batch_id']}/undo", headers=headers).status_code == 403


def test_candidate_import_undo_removes_only_untouched_work(env):
    client, (org1, _), engine, _ = env
    headers = login(client, "recruiter@example.test")
    job = make_job(client, org1, headers)
    commit = lambda: client.post(f"{BASE}/{org1}/candidate-imports/commit", files=csv_file(GOOD),
                                 data={"job_id": job, "consent_confirmed": "true"}, headers=headers).json()
    first = commit()
    undone = client.post(f"{BASE}/{org1}/candidate-imports/{first['batch_id']}/undo", headers=headers)
    assert undone.status_code == 200 and undone.json() == {"undone": 2, "removed_accounts": 1}
    with Session(engine) as db:
        assert db.scalar(select(func.count(Application.id))) == 0
        assert db.scalar(select(User.id).where(User.email == "asha@example.test")) is None
        assert db.scalar(select(User.id).where(User.email == "candidate@example.test")) is not None
    assert client.post(f"{BASE}/{org1}/candidate-imports/{first['batch_id']}/undo", headers=headers).status_code == 409
    # The jobs undo endpoint must not accept a candidates batch.
    assert client.post(f"{BASE}/{org1}/imports/{first['batch_id']}/undo", headers=headers).status_code == 404

    second = commit()
    application = client.get(f"/api/recruitment/organizations/{org1}/applications").json()[0]
    moved = client.patch(f"/api/recruitment/organizations/{org1}/applications/{application['id']}/stage",
                         json={"stage": "screening"}, headers=headers)
    assert moved.status_code == 200
    blocked = client.post(f"{BASE}/{org1}/candidate-imports/{second['batch_id']}/undo", headers=headers)
    assert blocked.status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(func.count(Application.id))) == 2, "a refused undo must change nothing"


def test_candidate_import_accepts_xlsx(env):
    client, (org1, _), _, _ = env
    headers = login(client, "recruiter@example.test")
    make_job(client, org1, headers, title="Workshop Lead")
    book = Workbook(); sheet = book.active
    sheet.append(["Full_Name", "Email", "Phone", "City", "Skills", "Job_Title"])
    sheet.append(["Meera Nair", "MEERA@example.test", 9810012345, "Kochi", "Diagnostics; Brakes", "workshop lead"])
    sheet.append([None, None, None, None, None, None])
    buffer = io.BytesIO(); book.save(buffer)
    files = {"file": ("people.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    body = client.post(f"{BASE}/{org1}/candidate-imports/preview", files=files).json()
    assert body["valid_count"] == 1 and body["errors"] == []
    assert body["sample"][0]["email"] == "meera@example.test"


def test_deletion_request_lifecycle(env):
    client, (org1, _), engine, cache = env
    recruiter = login(client, "recruiter@example.test")
    job = make_job(client, org1, recruiter)
    assert client.post("/api/privacy/deletion-requests", json={}, headers=recruiter).status_code == 403

    candidate = login(client, "candidate@example.test")
    application = client.post(f"/api/recruitment/jobs/{job}/apply", headers=candidate).json()["id"]
    assert client.post("/api/privacy/deletion-requests", json={}, headers={"origin": ORIGIN}).status_code == 403
    created = client.post("/api/privacy/deletion-requests", json={"reason": "No longer looking"}, headers=candidate)
    assert created.status_code == 201 and created.json()["status"] == "pending"
    assert client.post("/api/privacy/deletion-requests", json={}, headers=candidate).status_code == 409
    request_id = created.json()["id"]
    assert client.get("/api/admin-v3/deletion-requests").status_code == 403
    assert client.post(f"/api/admin-v3/deletion-requests/{request_id}/decision", json={"decision": "approve"},
                       headers=candidate).status_code == 403
    assert client.post(f"/api/privacy/deletion-requests/{request_id}/cancel", headers=candidate).json()["status"] == "cancelled"
    second = client.post("/api/privacy/deletion-requests", json={}, headers=candidate).json()["id"]
    candidate_cookie = client.cookies.get("im_hire_session")

    recruiter = login(client, "recruiter@example.test")
    client.post(f"/api/recruitment/organizations/{org1}/interviews", headers=recruiter,
                json={"application_id": application, "scheduled_at": "2027-01-01T10:00:00Z"})
    admin = login(client, "admin@example.test")
    pending = client.get("/api/admin-v3/deletion-requests", params={"status": "pending"}).json()
    assert [(r["id"], r["email"]) for r in pending] == [(second, "candidate@example.test")]
    assert client.post(f"/api/admin-v3/deletion-requests/{second}/decision", json={"decision": "maybe"},
                       headers=admin).status_code == 422
    approved = client.post(f"/api/admin-v3/deletion-requests/{second}/decision",
                           json={"decision": "approve", "note": "Verified by phone"}, headers=admin)
    assert approved.status_code == 200 and approved.json()["status"] == "completed"
    assert client.post(f"/api/admin-v3/deletion-requests/{second}/decision", json={"decision": "reject"},
                       headers=admin).status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(func.count(Application.id))) == 0
        assert db.scalar(select(func.count(Interview.id))) == 0
        assert db.scalar(select(func.count(CandidateProfile.id))) == 0
        assert db.scalar(select(User.id).where(User.email == "candidate@example.test")) is None
        erased = db.scalar(select(User).where(User.full_name == "Deleted account"))
        assert erased.active is False and erased.email.endswith("@deleted.invalid")
        row = db.execute(select(data_deletion_requests).where(data_deletion_requests.c.id == erased.id.__class__(second))).one()
        assert (row.status, row.decision_note) == ("completed", "Verified by phone")
    # The erased person's browser session is revoked and the old password no longer works.
    client.cookies.clear(); client.cookies.set("im_hire_session", candidate_cookie)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": "candidate@example.test", "password": PASSWORD},
                       headers={"origin": ORIGIN}).status_code == 401


def test_deletion_reject_keeps_data_and_staff_cannot_be_erased(env):
    client, (org1, _), engine, _ = env
    recruiter = login(client, "recruiter@example.test")
    job = make_job(client, org1, recruiter)
    candidate = login(client, "candidate@example.test")
    client.post(f"/api/recruitment/jobs/{job}/apply", headers=candidate)
    request_id = client.post("/api/privacy/deletion-requests", json={}, headers=candidate).json()["id"]
    admin = login(client, "admin@example.test")
    # The person became staff after asking: approval is refused until roles are removed.
    with Session(engine) as db:
        person = db.scalar(select(User.id).where(User.email == "candidate@example.test"))
        db.add(OrganizationMembership(user_id=person, organization_id=org1, role="interviewer")); db.commit()
    assert client.post(f"/api/admin-v3/deletion-requests/{request_id}/decision", json={"decision": "approve"},
                       headers=admin).status_code == 409
    rejected = client.post(f"/api/admin-v3/deletion-requests/{request_id}/decision", json={"decision": "reject"}, headers=admin)
    assert rejected.json()["status"] == "rejected"
    with Session(engine) as db:
        assert db.scalar(select(func.count(Application.id))) == 1
        assert db.scalar(select(User.active).where(User.email == "candidate@example.test")) is True


def test_enriched_lists_profile_and_analytics(env):
    client, (org1, org2), _, _ = env
    recruiter = login(client, "recruiter@example.test")
    job = make_job(client, org1, recruiter)
    assert client.get(f"/api/recruitment/organizations/{org1}/jobs/{job}").json()["title"] == "Python Developer"
    assert client.get(f"/api/recruitment/organizations/{org2}/jobs/{job}").status_code == 403

    candidate = login(client, "candidate@example.test")
    assert client.get("/api/recruitment/me/candidate-profile").json()["exists"] is False
    client.put("/api/recruitment/me/candidate-profile", headers=candidate,
               json={"phone": "98100", "city": "Pune", "skills": {"Welding": True}})
    assert client.get("/api/recruitment/me/candidate-profile").json() == {
        "exists": True, "phone": "98100", "city": "Pune", "skills": {"Welding": True}}
    application = client.post(f"/api/recruitment/jobs/{job}/apply", headers=candidate).json()["id"]
    assert client.get("/api/recruitment/me/applications").json()[0]["job_title"] == "Python Developer"
    assert client.get(f"/api/recruitment/organizations/{org1}/applications/{application}/history").status_code == 403

    recruiter = login(client, "recruiter@example.test")
    listed = client.get(f"/api/recruitment/organizations/{org1}/applications").json()[0]
    assert (listed["candidate_name"], listed["job_title"]) == ("Existing Candidate", "Python Developer")
    client.patch(f"/api/recruitment/organizations/{org1}/applications/{application}/stage",
                 json={"stage": "interview", "note": "Good call"}, headers=recruiter)
    history = client.get(f"/api/recruitment/organizations/{org1}/applications/{application}/history").json()
    assert [(h["previous_stage"], h["new_stage"]) for h in history] == [("applied", "interview"), (None, "applied")]
    assert history[0]["changed_by"] == "Recruiter"
    scheduled = client.post(f"/api/recruitment/organizations/{org1}/interviews", headers=recruiter, json={
        "application_id": application, "scheduled_at": "2027-01-01T10:00:00Z", "meeting_url": "https://meet.example.test/x"})
    assert scheduled.status_code == 201
    assert client.post(f"/api/recruitment/organizations/{org1}/interviews", headers=recruiter, json={
        "application_id": application, "scheduled_at": "2027-01-02T10:00:00Z", "meeting_url": "javascript:alert(1)"}).status_code == 422
    interview = client.get(f"/api/recruitment/organizations/{org1}/interviews").json()[0]
    assert (interview["candidate_name"], interview["job_title"], interview["feedback_count"]) == ("Existing Candidate", "Python Developer", 0)
    assert client.post(f"/api/recruitment/organizations/{org1}/interviews/{interview['id']}/feedback",
                       json={"score": 4, "comments": "Clear answers"}, headers=recruiter).status_code == 201
    notes = client.get(f"/api/recruitment/organizations/{org1}/interviews/{interview['id']}/feedback").json()
    assert [(n["reviewer"], n["score"]) for n in notes] == [("Recruiter", 4)]
    assert client.get(f"/api/recruitment/organizations/{org2}/interviews/{interview['id']}/feedback").status_code == 403
    stats = client.get(f"/api/recruitment/organizations/{org1}/analytics").json()
    assert stats["stages"] == {"interview": 1} and stats["job_statuses"] == {"published": 1} and stats["candidates"] == 1

    candidate = login(client, "candidate@example.test")
    mine = client.get("/api/recruitment/me/interviews").json()
    assert len(mine) == 1 and mine[0]["meeting_url"] == "https://meet.example.test/x"


def test_admin_user_and_member_management(env):
    client, (org1, _), engine, _ = env
    recruiter = login(client, "recruiter@example.test")
    assert client.get(f"/api/admin-v3/organizations/{org1}/members").status_code == 403
    admin = login(client, "admin@example.test")
    members = client.get(f"/api/admin-v3/organizations/{org1}/members").json()
    assert [(m["email"], m["role"]) for m in members] == [("recruiter@example.test", "recruiter")]
    users = {u["email"]: u["id"] for u in client.get("/api/admin-v3/users").json()}
    assert client.patch(f"/api/admin-v3/users/{users['admin@example.test']}", json={"active": False}, headers=admin).status_code == 409
    off = client.patch(f"/api/admin-v3/users/{users['recruiter@example.test']}", json={"active": False}, headers=admin)
    assert off.status_code == 200 and off.json()["active"] is False
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": "recruiter@example.test", "password": PASSWORD},
                       headers={"origin": ORIGIN}).status_code == 401
    admin = login(client, "admin@example.test")
    removed = client.delete(f"/api/admin-v3/organizations/{org1}/members/{users['recruiter@example.test']}", headers=admin)
    assert removed.status_code == 200
    with Session(engine) as db:
        assert db.scalar(select(func.count(OrganizationMembership.id)).where(OrganizationMembership.organization_id == org1)) == 0


def test_migration_0003_is_additive_and_chained():
    source = Path("alembic/versions/0003_phase3_completion.py").read_text(encoding="utf-8")
    assert 'down_revision = "0002_phase3_admin"' in source
    upgrade = source[source.index("def upgrade"):source.index("def downgrade")]
    assert "drop_" not in upgrade
    for name in ("user_id", "application_id", "created_user", "reason", "decided_by_id", "decided_at", "decision_note"):
        assert f'"{name}"' in upgrade
    assert {c.name for c in import_rows.c} >= {"user_id", "application_id", "created_user"}
    assert "rev!='0003_phase3_completion'" in Path("scripts/verify_phase3.py").read_text(encoding="utf-8")
