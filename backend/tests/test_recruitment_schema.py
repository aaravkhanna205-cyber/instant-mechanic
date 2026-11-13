"""No external DB required: validation and relational smoke test in SQLite."""
import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.models.schema import Base, Organization, User, OrganizationMembership, Job, CandidateProfile, Application, JobCategory
from app.models.categories import OFFICIAL_ROLES, seed_official_roles


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def test_schema_has_expected_tables_and_foreign_keys(db):
    names = set(inspect(db.bind).get_table_names())
    # The Interview Studio adds three tables of its own; the original schema stays at 16.
    assert len({t for t in (names - {"interview_questions", "interview_answers", "interview_reports"}) if not str(t).startswith("phase6_")}) == 16
    assert {"organizations", "users", "jobs", "applications", "interviews", "audit_logs"} <= names
    fks = inspect(db.bind).get_foreign_keys("applications")
    assert {f["referred_table"] for f in fks} >= {"jobs", "candidate_profiles"}


def test_seed_exact_11_roles_is_idempotent(db):
    assert len(OFFICIAL_ROLES) == 11
    assert seed_official_roles(db) == 11
    assert seed_official_roles(db) == 0
    assert len(db.scalars(select(JobCategory.slug)).all()) == 11


def test_organization_job_candidate_application_workflow(db):
    seed_official_roles(db)
    org = Organization(name="Instant Mechanic", slug="instant-mechanic")
    recruiter = User(email="recruiter@example.test", full_name="Recruiter", password_hash="test-hash")
    candidate = User(email="candidate@example.test", full_name="Candidate", password_hash="test-hash")
    db.add_all([org, recruiter, candidate]); db.flush()
    membership = OrganizationMembership(user_id=recruiter.id, organization_id=org.id, role="recruiter")
    profile = CandidateProfile(user_id=candidate.id, skills={"python": True})
    db.add_all([membership, profile]); db.flush()
    job = Job(organization_id=org.id, created_by_id=recruiter.id, category_slug="python-tool-developer", title="Python Tool Developer", status="draft")
    db.add(job); db.flush()
    application = Application(job_id=job.id, candidate_id=profile.id, stage="applied")
    db.add(application); db.commit()
    assert db.scalar(select(Application).where(Application.job_id == job.id)).candidate_id == profile.id


def test_stage_constraints_declared():
    assert any('trade_test' in str(c.sqltext) for c in Application.__table__.constraints if hasattr(c, 'sqltext'))
