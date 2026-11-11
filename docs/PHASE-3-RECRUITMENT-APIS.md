# Phase 3 — Recruitment API milestone

This milestone adds **database-backed recruitment APIs** to the existing FastAPI app. It reuses the already migrated 16-table schema and existing Redis-backed session authentication. **It does not modify Next.js pages or create a new migration.**

## Scope

- Public official job categories and published vacancies
- Platform-admin organization creation, organization listing for authorized users
- Recruiter-scoped jobs creation/listing/editing
- Candidate profile self-service and self-service application to published vacancies
- Recruiter-scoped candidate and application listing; tracked hiring stages
- Interviews, feedback, basic analytics, audit logs
- CSV import, email notifications, resume uploads, rich analytics and Phase 2 frontend wiring **not included in this package**

All changing operations require a logged-in session and the `X-CSRF-Token` value returned by `/api/auth/me` or `/api/auth/login`. Client requests must use `credentials: "include"` and a backend-allowed frontend origin. The API deliberately returns minimal candidate fields. All recruiter operations check organization membership, while platform admins may access all organizations.

## Install and verify

From the **Git repository root**, execute the extracted `Install-Phase3-Recruitment.ps1` after reviewing it. It requires a clean Phase 3 development branch and makes a timestamped backup of the **existing backend/app/main.py** before changing it. It refuses to overwrite existing recruitment API files and leaves all environment files, Docker volumes, and recruitment database tables untouched.

Then run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.seed_job_categories
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check `/api/ready` and `/docs`. The official role seeder can safely be run repeatedly; it adds only categories that are missing and does not create real job vacancies.

### End-to-end browser checks

1. Log in via `/auth-live` and confirm `/api/auth/me` succeeds.
2. As platform admin, create an organization using `/docs`, adding the session CSRF header. **The Swagger UI might not have a logged-in browser cookie when opened on a different host (`localhost` versus `127.0.0.1`).**
3. Create a draft job in that organization and publish it.
4. Use public jobs to check it is discoverable.
5. As a separately created candidate account, apply to it; check that the application is visible under `/me/applications`.
6. As recruiter/admin, change the application stage, schedule an interview, add feedback and check counts.
7. Confirm a recruiter from another organization receives 403 and a candidate cannot read organization-only lists.

**Important:** `bootstrap_admin` creates only the first admin. Candidate self-registration and recruiter invitation are not included in this API milestone; test with pre-provisioned accounts. Do not create new users using raw SQL or share credentials in chat.

## Git checkpoint

From the repository root after local tests and browser workflow verification:

```powershell
git add backend/app/api/recruitment.py backend/scripts/seed_job_categories.py backend/tests/test_recruitment_api.py backend/app/main.py docs/PHASE-3-RECRUITMENT-APIS.md
git --no-pager diff --cached --name-only
git commit -m "feat: add organization-scoped recruitment APIs"
git push origin HEAD
```

Before committing, confirm no `.env`, password, session, virtualenv, or backup paths are staged.
