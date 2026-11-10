# Phase 2 — Recruitment screens (demo)

This is an **overlay update** for the existing Instant Mechanic Hire workspace. It intentionally leaves `backend/`, `.env` files, `package.json`, `package-lock.json`, `README.md`, and all Git metadata untouched.

## Added interactive routes

- `/jobs`: job list with text search, status filters, and applicant counts
- `/jobs/new`, `/jobs/[id]`, `/jobs/[id]/edit`: job form, editing, publishing status, Kanban-style stage board and stage updates
- `/candidates`: searchable candidate table
- `/candidates/upload`: PDF/DOCX extensions and 5 MB max; supports multiple file selection and metadata-only demo intake. **File bytes are not read or uploaded.**
- `/candidates/[id]`: profile, tagged skills, indicative skill match, editable recruiter notes
- `/interviews`: proposed appointments and status updates (no invites sent)
- `/analytics`: demo pipeline and KPI charts
- `/portal`: mobile-friendly candidate job discovery, demo resume-only application and demo application tracker
- `/admin`: demo settings, audit log, user management and import previews

## Data isolation warning

The demo uses browser `localStorage` shared across screens. It does **not** provide access control or candidate-specific privacy. **Never enter real candidate names, resumes, email addresses, telephone numbers, or other personal data into Phase 2.** Replace with a secure, organization-scoped backend during Phase 3 before using real information.

## Not yet implemented

- True file storage, PDF/DOCX parsing, RAG, AI evidence generation, candidate ranking (prohibited), or live interview calls
- Multi-user authentication/authorization, invitations, actual sending or booking, persistent PostgreSQL records
- Drag-and-drop Kanban, real import/undo, voice interviews, full mobile/browser automated testing
- Production deployment or accessibility certification

## Validation (Windows)

```powershell
cd frontend
npm run lint
npm run typecheck
npm run build
npm run dev
```

On Windows where SWC native bindings fail and Webpack has already been configured, `npm run build` uses Webpack. Otherwise `npx next build --webpack` is a fallback.

Open `http://localhost:3000/jobs`, create a demo role, move an application between stages, submit a *fake* application via `/portal`, and inspect `/analytics` and `/admin`. Refresh; demo records should persist in that browser.

## Git workflow

From the **existing repository root**, run:

```powershell
git status
git add frontend docs/PHASE-2-IMPLEMENTATION.md
git commit -m "feat: add phase 2 recruitment demo workflows"
git push origin main
```

Inspect `git status` before committing; don't commit `node_modules`, `.next`, `.env` or files containing personal data.
