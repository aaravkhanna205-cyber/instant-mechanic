# Instant Mechanic Hire — Phase 3 Schema Milestone

This **schema-only** milestone adds 16 recruitment tables and 11 official role categories. It does **not** add login endpoints, create users, publish vacancies, perform file uploads, or integrate the Phase 2 demo UI. PostgreSQL stores one row per category; no jobs are automatically published.

## Requirements

- Current branch: `phase3-rebuild-*`; clean Git working tree before running installer
- Phase 3 Fresh Foundation installed and `/api/ready` returns PostgreSQL and Redis `true`
- The **fresh** PostgreSQL database is empty of previous application tables. If you have existing recruitment data, do not run this initial migration: it is not a data-preserving upgrade from the old Phase 3 schema.
- Python backend environment has SQLAlchemy, Alembic, pytest and psycopg available

## Commands (from existing project root)

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install 'alembic>=1.13,<2'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m scripts.check_schema
```

The installer includes an explicit preflight SQL query and refuses to run the migration if it finds existing schema tables or an Alembic revision. Database migrations are **not applied automatically** by the installer.

## Tables

`organizations`, `users`, `organization_memberships`, `job_categories`, `candidate_profiles`, `recruiter_profiles`, `jobs`, `job_requirements`, `resumes`, `applications`, `application_stage_history`, `interviews`, `interview_feedback`, `audit_logs`, `user_consents`, `notifications`.

> Count: **16** application tables, plus Alembic's `alembic_version` after applying the migration.

## Next milestone

Argon2 password hashing, explicit permission checks and authentication endpoints; then live recruitment APIs and frontend integration. No role is trusted solely from a client request.
