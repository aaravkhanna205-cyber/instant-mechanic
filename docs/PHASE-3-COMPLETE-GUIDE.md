# Instant Mechanic Hire — Phase 3 completion

Branch: `phase3-completion` (built on `phase3-rebuild-20261111-095645`).

Phase 3 is the backend, login and the live screens. After this branch the whole
workspace reads and writes PostgreSQL; no screen shows demo data any more.

## What this branch adds

Backend
- **Candidate import** (CSV/XLSX): read-only preview, all-or-nothing commit, undo.
  Each row becomes an application at the *Applied* stage for a vacancy.
  Columns: `full_name,email` (required), `phone,city,skills,job_title` (optional).
  New people get an account **without a password**; they set one with "Forgot password".
- **Data-deletion requests**: a candidate asks, a platform admin approves or rejects.
  Approval deletes profile, applications and interviews, anonymizes and closes the account.
- **Migration `0003_phase3_completion`**: additive columns on `import_rows` and
  `data_deletion_requests`. No table is dropped or rewritten.
- Richer lists (candidate and vacancy names on applications and interviews), stage
  history, stage and status counts in analytics, own profile and interviews for
  candidates, interview feedback list, member list, remove member, deactivate account.
- Interview meeting links must start with `http://` or `https://`.

Frontend
- `/dashboard`, `/jobs`, `/candidates`, `/interviews`, `/analytics`, `/admin` are live.
- `/jobs/import` and `/candidates/upload` are the two spreadsheet imports.
- `/portal` (overview, vacancies, applications, interviews) is the live candidate portal.
- `/login`, `/register`, `/forgot-password`, `/reset-password` are live.
- Old addresses still work: `/auth-live` is the sign-in page, `/phase3` opens the
  dashboard, `/phase3/candidate` opens the portal.
- `/agents` and `/approvals` stay as Phase 6 previews.

## Commands

Start PostgreSQL and Redis first (project root):

```powershell
docker compose --env-file .phase3-fresh.env -f compose.phase3-fresh.yml up -d
```

Backend, with the virtual environment active:

```powershell
cd backend
python -m pip install -r requirements-phase3-completion.txt
python -m pytest -q
python -m alembic upgrade head
python -m scripts.verify_phase3
python -m scripts.seed_job_categories
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`alembic upgrade head` must print `Running upgrade 0002_phase3_admin -> 0003_phase3_completion`
the first time. `verify_phase3` must end with `PHASE 3 DATABASE READY`.

Frontend, in a second terminal:

```powershell
cd frontend
npm install
npm run typecheck
npm run lint
npm run dev -- --hostname 127.0.0.1 --port 3000
```

`frontend\.env.local` needs `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`.
`backend\.env` needs the frontend address in `CORS_ORIGINS`. Never commit either file.

## Acceptance checks in the browser

1. Open `/dashboard` while signed out: you land on `/login`.
2. Sign in as the platform admin. With no organization, open Super Admin → Organizations and create it.
3. Jobs → New vacancy → save → Publish. Refresh: it is still there.
4. Jobs → Import jobs: a file with a wrong `category_slug` is refused whole; a clean file imports drafts; Undo removes them.
5. Candidates → Import candidates: pick a default vacancy, preview, tick the confirmation, import. Both people appear under Candidates.
6. Open a candidate: move the stage with a note, schedule an interview, open the stage history.
7. Interviews → open the interview → save feedback.
8. Register a new candidate at `/register`, sign in: you land on `/portal`, and `/dashboard` sends you back to the portal.
9. In the portal: save the profile, apply to the vacancy, check My applications, then ask to delete your data.
10. As admin: Super Admin → Deletion requests → Approve. The person disappears from Candidates and can no longer sign in.
11. Super Admin → People and roles: assign a registered person the recruiter role; sign in as them and confirm they see only their organization.

## Still open

- **Password reset email** needs `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
  `SMTP_FROM` and an HTTPS `RESET_URL_BASE` in `backend\.env`. Until then imported people
  cannot set a password, and "Forgot password" answers that email is not set up.
- **Consent and retention wording** must be checked by a lawyer (India's DPDP Act).
  The deletion workflow is provided; the legal text is not.
- **Resume upload** is Phase 4. Candidates currently apply with their profile only.
- Audit log and account lists show the latest 100 and 200 entries; paging is not built.

## Safety

- Do not run `docker compose down -v` or `alembic downgrade` on data you want to keep.
- Never commit `.env` files. No automated rejection, scoring or hiring decisions exist anywhere.
