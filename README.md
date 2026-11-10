# Instant Mechanic Hire — single-workspace monorepo

Internal recruitment software for Instant Mechanic. **One ZIP and one VS Code workspace for every phase.**

## Current implementation status

- **Phase 0:** Workspace, repo structure, scripts, environment templates and local service configuration are included. Existing frontend audited at a structural level; full automated checks remain to be run locally.
- **Phase 1:** Next.js frontend starter with recruiter dashboard, demo data, rebrand theme, auth UI and preview navigation included. **Verify lint, typecheck, build and browser responsiveness locally.**
- **Phases 2–8:** Folder structure, project plans, API skeleton and service configuration have been prepared. **Feature implementation, security review and production deployment are NOT finished.** The future features are not claimed to work yet.

## Requirements

Node.js 20.9+, npm, Python 3.11+, Git. Docker Desktop is optional for Phase 1, required for the local PostgreSQL/Redis environment in Phase 3.

## Start Phase 1 (Windows PowerShell)

```powershell
cd frontend
npm install
npm run lint
npm run typecheck
npm run build
npm run dev
```

Open http://localhost:3000/dashboard. Authentication buttons are **UI preview only** until Phase 3. Later-phase menu items are intentionally labelled preview.

## Work in this folder forever

Return to the repository root after running frontend commands:

```powershell
cd ..
git init
git branch -M main
git remote add origin https://github.com/aaravkhanna205-cyber/instant-mechanic.git
git add .
git commit -m "feat: initial monorepo and phase 1 frontend"
git push -u origin main
```

Only use `git remote add` if `git remote -v` is empty. On future changes, use `git add .`, `git commit -m "..."`, `git push` in this *same* repo. No extra ZIP extraction.

## Later-phase entry points

- `backend/` — FastAPI skeleton; `pip install -r backend/requirements.txt`, then `uvicorn app.main:app --reload --app-dir backend` from repo root, or run `uvicorn app.main:app --reload` inside backend.
- `docker-compose.yml` — planned local Postgres/pgvector and Redis; `docker compose up -d` when Phase 3 begins.
- `.env.example`, `backend/.env.example`, `frontend/.env.example` — variable names only, no real passwords or access keys.
- `docs/PHASES.md`, `docs/ARCHITECTURE.md` — full build sequence and acceptance gates.
- `scripts/` — PowerShell helpers. Do not execute scripts with admin privileges.

## Security & hiring principles

No automated candidate rejection or hidden suitability scoring. Every send, booking and hiring decision requires human review. Resume content is untrusted data. Candidate uploads will be PDF/DOCX only, private, and access controlled. Do not store private candidate files or tokens in Git. Organization isolation and audit logs must be enforced in the backend when those capabilities are implemented.

This is a development scaffold, **not** a completed production platform.
