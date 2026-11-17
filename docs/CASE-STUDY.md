# Case study: Instant Mechanic Hire

**An internal hiring platform for a roadside-assistance company, built phase by phase and self-hosted for free.**

## The problem

Instant Mechanic hires mechanics, support staff and office roles across several cities. Applications arrived
through calls, messages and forwarded resumes. Nobody could see who had applied for what, which stage each
person was in, or whether a candidate had been told anything. The hiring manager had no HR background, and
the company did not want to pay for a recruitment SaaS or a cloud server.

## Goals

1. One place where every applicant, resume, stage and interview lives.
2. Clear roles: an HR manager and a hiring manager with full access, a Super Admin, simple access for candidates.
3. Candidates always know where they stand, in simple English, on a phone.
4. AI that saves time but never makes the decision.
5. Zero running cost: one Windows PC, free software, public HTTPS.

## What was built

| Phase | Result |
|---|---|
| 1-2 | Next.js front end in the company's yellow / orange / white style; project structure |
| 3 | PostgreSQL schema, Argon2id sign-in, sessions with CSRF protection, role checks per organization, jobs, applications, stage history, interviews |
| 4 | Resume upload with type checks and ClamAV virus scanning, text extraction, skills, pgvector evidence search |
| 5 | Docker production setup, Caddy proxy, self-hosting on the PC behind Tailscale Funnel, backups, verification script |
| 6 | Human-approved AI agents: resume review, interview summary, job description, analytics, with checkpoints and allowlisted tools |
| 7 | HR manager and hiring manager roles, team management, candidate notifications and emails, search, reports, CSV exports, retention, Super Admin, candidate portal next steps |
| 8 | Resume-before-apply rule, Gmail delivery, server-error log, security and browser test suites, CI, automatic start and daily backups with restore test, documentation |

## Key decisions

- **Self-hosted instead of cloud.** Docker Desktop + Tailscale Funnel gives a stable HTTPS address with no bill.
  The trade-off (the PC must stay on) is acceptable for an internal tool and written down in KNOWN-LIMITS.
- **Resume upload only.** Candidates do not fill long forms; one PDF or Word file is enough, and it is required before applying.
- **Human in the loop.** Every AI output is a proposal that a person approves; no automatic ranking or rejection.
  This keeps decisions explainable and fair.
- **Security by default.** HttpOnly + Secure cookies, CSRF tokens, origin checks, login lockout, organization
  isolation, virus scanning, consent before reading resumes, data deletion and retention, a secret scan in CI.
- **Plain language everywhere.** Stage names come with one-line explanations for candidates; guides are written for non-HR staff.

## Quality

- About 135 automated backend tests, including a release suite for permissions, uploads, cookies and CSRF.
- Browser tests (Playwright) for the full hiring story from registration to the HR email log.
- Database migrations tested up, down and up on PostgreSQL; fresh installs and upgrades both work.
- GitHub Actions runs everything on each push.

## Stack

FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 17 + pgvector, Redis, ClamAV, Next.js (App Router, TypeScript),
Tailwind CSS, Caddy, Docker Compose, Tailscale Funnel, Playwright, pytest, GitHub Actions, optional Ollama.

## What I learned

- Writing the permission rules once (`roles.py`) and testing them from the outside caught mistakes early.
- The hard part of self-hosting is not starting the app but keeping it running: automatic start, backups that
  are proven by a restore test, and a health page anyone can read.
- Recruitment software is mostly communication: the biggest improvement for candidates was being told what
  each stage means.
