"""Canonical role categories. Records are examples; no active vacancies are auto-created."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.schema import JobCategory

OFFICIAL_ROLES = (
    ("customer-support-executive", "Customer support executive", "Customer Support"),
    ("mechanic", "Mechanic", "Workshop"),
    ("technician", "Technician", "Workshop"),
    ("service-advisor", "Service advisor", "Customer Operations"),
    ("python-tool-developer", "Python tool developer", "Technology"),
    ("office-assistant", "Office assistant", "Administration"),
    ("accountant", "Accountant", "Finance"),
    ("research-analyst", "Research Analyst", "Research"),
    ("operations-executive", "Operations executive", "Operations"),
    ("engineer", "Engineer", "Engineering"),
    ("full-stack-developer", "Full stack developer", "Technology"),
)


def seed_official_roles(session: Session) -> int:
    """Idempotent; does not overwrite customized descriptions/departments."""
    existing = set(session.scalars(select(JobCategory.slug)).all())
    missing = [JobCategory(slug=s, title=t, department=d) for s,t,d in OFFICIAL_ROLES if s not in existing]
    session.add_all(missing)
    session.flush()
    return len(missing)
