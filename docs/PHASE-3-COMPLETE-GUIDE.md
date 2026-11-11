# Instant Mechanic Hire — Phase 3 consolidation

## Intended branch
`phase3-rebuild-20261111-095645`. This update assumes the existing FastAPI foundation, the `0001_fresh_schema` migration (16 tables), the Phase 3 authentication package and associated dependencies. It does not modify the earlier Phase 2 demo screens.

## Changes
- Recruitment endpoints, hiring stages, organization-scoped jobs/candidates/interviews/analytics and official roles
- Self-service candidate registration, recruiter role assignment by the platform admin
- Six admin tables in migration `0002_phase3_admin`, total 22 application tables
- Platform-admin users/settings/audit endpoints
- CSV/XLSX **jobs-only** import with read-only preview, row validation, drafts-only commit, undo subject to no applications or status changes
- SMTP-backed password reset routes (requires SMTP setup; cannot function until configured)
- New `/phase3` live recruiter/admin workspace, `/phase3/candidate` self-service portal, `/phase3/register` registration screen, shared typed API client

## Important scope / constraints
This update is not verified on your own Windows system until commands and browser tests succeed. The existing `/admin`, `/dashboard`, `/jobs`, `/candidates`, `/interviews` Phase 2 pages remain demo/mock content and are NOT silently described as live. The new `/phase3` route is live and uses the same yellow-orange-white palette. Resumes and AI intelligence belong to Phase 4; uploading and parsing PDF/DOCX files is not implemented here. SMTP must be configured for password reset. Only job CSV/XLSX import is implemented; bulk candidate import is still not implemented. These are known outstanding roadmap items, so do not claim full Phase 3 acceptance until they are addressed.

## Commands (project root)
```powershell
# After installer
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-phase3-completion.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.verify_phase3
.\.venv\Scripts\python.exe -m scripts.seed_job_categories
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# separate terminal
cd frontend
npm run typecheck
npx next build --webpack
npm run dev -- --hostname 127.0.0.1 --port 3000
```
The frontend `.env.local` should set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`; backend `.env` should allow the exact frontend origin in `CORS_ORIGINS`. Never commit either file. Keep PostgreSQL and Redis running.

## Live tests
1. `/api/ready` confirms PostgreSQL and Redis.
2. Bootstrap platform admin if none exists, using `python -m scripts.bootstrap_admin` (never put passwords on CLI).
3. Log in at `/auth-live`; open `/phase3`; create an organization.
4. Create a draft job using an official role, publish it, refresh and verify persistence.
5. Register a candidate at `/phase3/register`, sign in, create a profile and apply at `/phase3/candidate`.
6. As a recruiter, verify candidate and application visibility scoped to the organization; move the application stage, schedule an interview.
7. As platform admin, verify users, role assignments, settings, audit history.
8. Upload a small CSV (headers: `title,category_slug,description,location`), preview, commit draft jobs, then undo. Test a bad category row and confirm import rejected without partial writes.
9. Log out; confirm that protected data cannot be accessed. Use a second org/candidate to verify 403/404 isolation.
10. Run `Verify-And-Push-Phase3.ps1` after completing browser checks. Supply `-Push` only when ready to stage, commit and push your branch.

## SMTP password reset (optional until mail credentials are available)
Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, and `RESET_URL_BASE` as server-side environment variables (not `NEXT_PUBLIC_*`). `RESET_URL_BASE` must be HTTPS. This package supplies API endpoints but no hosted email provider; reset UI is at `/phase3/reset-password`; plan production testing before enabling.

## Security warnings
- `APP_ENV=production` changes cookie to secure SameSite=None; this requires HTTPS, correct CORS and cross-origin cookie policy. Prefer same-site frontend/API deployment or a Next.js same-origin proxy.
- Never commit `.env` or secrets; a local `.gitignore` does not remove previously committed secrets from history.
- Do not use `docker compose down -v` or migrate down on your working data.
- No automated candidate rejection, scoring or hiring decisions.
