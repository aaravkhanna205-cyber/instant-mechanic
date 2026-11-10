# Development stages — source roadmap (10 November 2026)

This repository holds **all phase directories from day one**. A prepared folder does NOT mean the feature is implemented. Update the status after tests and human acceptance. The original roadmap has 9 phases (0–8) and 45 coding steps.

| Phase | Steps | Deliverable | State at first ZIP |
|---|---:|---|---|
| 0. Setup and audit | 1–2 | workspace, dependencies, baseline Git, run verification | Partially prepared |
| 1. Frontend foundation | 3–9 | branded theme, reusable UI, shell, auth mock screens, recruiter dashboard | Starter implementation; validation pending |
| 2. Recruitment screens | 10–14 | jobs, candidates, interviews, candidate portal, super admin mock UI | Not implemented |
| 3. Backend + login | 15–26 | PostgreSQL, Redis, FastAPI, 22 tables, sessions, org checks, API, import | API health skeleton and Compose prepared only |
| 4. Resume intelligence | 27–32 | private PDF/DOCX upload, extraction, RAG, evidence with citations | Not implemented |
| 5. Interviews | 33–36 | scheduling, consent, text/optional voice, evaluation | Not implemented |
| 6. AI agents | 37–39 | LangGraph, tools allowlist, approvals, workflow audit | Not implemented |
| 7. Organizations | 40–42 | six roles, multi-tenancy, notifications, retention, admin | Not implemented |
| 8. Test and deploy | 43–45 | CI, testing, Docker, Render + Vercel + Neon + Redis, monitoring | Initial Dockerfiles only; NOT deployed |

## Essential constraints

- Hiring is for Instant Mechanic itself, not a commercial SaaS.
- Candidate applies only by PDF/DOCX resume upload.
- AI produces supported / unclear / missing evidence, not ranking or automatic rejection.
- Every email, booking and hiring decision has human approval.
- Interview consent is a prerequisite.
- Candidate and organization authorization are server-side, audited and tested.
- Super Admin edits through the UI once implemented.

## Phase 1 completion gate

- [ ] `npm install` works with Node 20.9+
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes
- [ ] Dashboard and auth URLs load
- [ ] Sidebar, theme and forms checked on mobile (375px) and desktop (1440px)
- [ ] Preview labels clearly identify nonfunctional later-phase actions
- [ ] Push same repository to GitHub

## Later-phase gates

For each phase, add implementation files *inside this repository*, execute the relevant tests, and commit. Do not unzip another project and do not run migrations before they exist. Do not replace secrets with actual values in tracked files.
