# Instant Mechanic Hire

Instant Mechanic's own hiring platform: candidates apply with a resume, the HR manager and hiring manager
review, shortlist, interview and decide, and every candidate is kept informed by email and in their portal.
It runs **free, on one Windows PC**, with a public HTTPS address through Tailscale Funnel. No cloud account is needed.

Yellow / orange / white design. Works on phones (candidates) and desktops (staff).

## Who does what

| Person | Role in the app | What they can do |
|---|---|---|
| Super Admin | Platform admin | Everything, for every organization: people, roles, data retention, system health, settings |
| Neeraj | HR manager | Full access: jobs, candidates, interviews, decisions, team, candidate emails, reports, exports |
| Aarav Khanna | Hiring manager | Full access: interviews, shortlisting, hiring decisions, team, reports, exports |
| Recruiter (optional) | Recruiter | Jobs, candidates, interviews, AI agents; cannot manage the team |
| Interviewer (optional) | Interviewer | Assigned interviews and feedback |
| Applicants | Candidate | Candidate portal: upload resume, apply, follow progress, answer interview invitations |

## What is inside

- **Candidate portal** - register, upload a resume (PDF or Word, scanned for viruses), apply, see each stage explained in plain words, confirm interviews, ask for data deletion.
- **Staff workspace** - jobs, candidates, stage changes with notes and history, interview scheduling and feedback, Interview Studio, analytics, reports and CSV exports, team and roles, notifications.
- **AI assistance (human-approved)** - resume reading and evidence, interview question drafts, four agent workflows (resume review, interview summary, job description, analytics). Nothing is decided automatically.
- **Emails** - candidates get an email when they apply, change stage or get an interview. Sent from Gmail when switched on.
- **Operations** - one-command start, health checks, server-error log, daily backups with restore test, automatic start after sign-in.

## Quick start (the PC that hosts the site)

Full steps: [docs/WINDOWS-SETUP.md](docs/WINDOWS-SETUP.md). Short version, in PowerShell in the project folder:

```powershell
.\scripts\selfhost.ps1 -PublicUrl https://YOUR-PC.YOUR-TAILNET.ts.net   # first time
.\scripts\selfhost.ps1            # every later start
.\scripts\selfhost.ps1 -Verify    # checks everything
.\scripts\selfhost.ps1 -Backup    # backup now
.\scripts\windows-tasks.ps1 -Install   # start by itself + daily backup
.\scripts\email-setup.ps1         # send real emails from Gmail
```

## Documents

| Read this | For |
|---|---|
| [docs/WINDOWS-SETUP.md](docs/WINDOWS-SETUP.md) | Installing and running it on the Windows PC |
| [docs/GMAIL-SETUP.md](docs/GMAIL-SETUP.md) | Switching on real emails from Gmail |
| [docs/HR-MANAGER-GUIDE.md](docs/HR-MANAGER-GUIDE.md) | Neeraj: daily work, emails, reports, team |
| [docs/HIRING-MANAGER-GUIDE.md](docs/HIRING-MANAGER-GUIDE.md) | Aarav: shortlisting, interviews, decisions |
| [docs/CANDIDATE-GUIDE.md](docs/CANDIDATE-GUIDE.md) | Simple guide to share with applicants |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the parts fit together |
| [docs/TESTING.md](docs/TESTING.md) | Automatic tests, browser tests, CI |
| [docs/KNOWN-LIMITS.md](docs/KNOWN-LIMITS.md) | What it does not do (yet) |
| [docs/CASE-STUDY.md](docs/CASE-STUDY.md) | Portfolio write-up of the project |
| [docs/PHASE8-RELEASE.md](docs/PHASE8-RELEASE.md) | What Phase 8 added and how to upgrade |

Earlier phase notes stay in `docs/` (PHASE-3 to PHASE7) for history.

## Code layout

```
backend/    FastAPI + SQLAlchemy + Alembic (Python). Tests in backend/tests
frontend/   Next.js website. Browser tests in frontend/e2e
scripts/    PowerShell scripts for the Windows PC, secret scan
deploy/     Caddy proxy settings
compose.*.yml  Docker setups (database, app, self-hosting)
```

Private settings live only on the PC in `.env.phase5.local` and `.phase3-fresh.env` and are never committed
(`python scripts/secret_scan.py` checks this, also in CI).
