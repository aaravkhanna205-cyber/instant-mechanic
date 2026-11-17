# Architecture

Everything runs in Docker Desktop on one Windows PC. Tailscale Funnel gives it a fixed public HTTPS address.

```
Candidate / staff browser
        |  HTTPS  (https://NAME.TAILNET.ts.net, Tailscale Funnel)
        v
  proxy  (Caddy, 127.0.0.1:13080)  -- adds security headers, 10 MB upload limit
    |-- /api/*  -> api   (FastAPI, Python)          -> PostgreSQL 17 + pgvector  (127.0.0.1:55433)
    |                                                -> Redis 7 (sessions, queues) (127.0.0.1:56380)
    |                                                -> ClamAV (virus scan of every upload)
    |                                                -> Ollama on the PC (optional, local AI drafts)
    '-- /*      -> web   (Next.js website)

  worker        reads uploaded resumes (text, skills, evidence chunks with embeddings)
  p6-scheduler  plans agent tasks (reminders, follow-ups)
  p6-worker     sends agent messages and candidate notification emails (outbox or Gmail SMTP)
```

| Container / service | Started by | Purpose |
|---|---|---|
| postgres, redis | `compose.phase3-fresh.yml` | Data and sessions. Restart by themselves. |
| api, web, worker, p6-scheduler, p6-worker | `compose.phase5-app.yml` | The application |
| proxy, clamav | `compose.selfhost.yml` | Public entry point and virus scanning |

## Backend (backend/app)

| Folder | What it holds |
|---|---|
| `api/` | Sign-in, registration, password reset, jobs, applications, stages, interviews, privacy, imports |
| `security/` | Sessions (HttpOnly cookie + CSRF token), passwords (Argon2id), roles (`roles.py`) and permission checks |
| `phase4_ai/` | Resume upload, validation, virus scan, reading, evidence search |
| `interview_studio/` | Approved question sets, candidate answers, review report |
| `phase6_agents/`, `ai/agents/workflows/` | Human-approved agents and the four workflows (checkpointed, allowlisted tools) |
| `phase7/` | Team and roles, notifications and candidate emails, search, reports, CSV exports, retention, health |
| `phase8/` | Server-error log (`monitoring.py`) and the Gmail test command (`test_email.py`) |

Database changes are Alembic migrations in `backend/alembic/versions` (0001 to 0012). Apply with
`docker exec imhire_phase5_app-api-1 python -m alembic upgrade head`.

## Security in short

- Passwords hashed with Argon2id; sign-in locks for 15 minutes after 8 wrong tries.
- Session cookie is HttpOnly, Secure (in production) and checked against a CSRF token on every change.
- Only our own website address may call the API (origin check); API docs are not public.
- Every request checks the person's role in that organization; staff of one organization cannot see another.
- Uploads: PDF/DOCX only, real file type checked, 8 MB limit, virus scan before anything is saved.
- Candidates must agree before their resume is read; they can ask for deletion; retention clean-up for old data.
- Server errors are logged without personal data (page address and error type only, 30 days).
- AI never decides: every agent result waits for a person to approve.

## Frontend (frontend/)

Next.js App Router. `components/live/*` are the real screens; `lib/live` holds the session and data hooks;
`lib/api/phase3.ts` holds the API types and role lists. Theme colors: yellow #FBBF24, orange #F97316,
deep orange #C2410C, background #FFFCF7.
