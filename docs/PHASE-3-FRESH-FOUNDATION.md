# Instant Mechanic Hire — Phase 3 Fresh Foundation

This is **step 18 / foundation**, NOT a completed Phase 3 implementation. It preserves existing Phase 1–2 frontend routes.

## Included
- FastAPI `GET /api/health` liveness endpoint, `GET /api/ready` that checks PostgreSQL and Redis.
- Separate, isolated development compose file with pgvector PostgreSQL and Redis.
- Safe local `.env` creation by installer, no hardcoded passwords or API keys.
- FastAPI/Redis/PostgreSQL dependencies and tests for health, readiness and CORS.

## Not yet included
- Alembic migrations / 22-table production schema, sessions, auth, role checks, hiring APIs, or live frontend integration.
- No API key required for this foundation. Configure secrets for later stages via server secret settings.

## Commands (PowerShell, from project root)

```powershell
# First confirm Docker Desktop is running and ports 55433 and 56380 are available.
docker compose --env-file .phase3-fresh.env -f compose.phase3-fresh.yml up -d
docker compose --env-file .phase3-fresh.env -f compose.phase3-fresh.yml ps
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Use `python -m venv .venv` if Python 3.12 launcher is unavailable. `pip install` may need internet access.

In another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/ready
```

Expected readiness response contains `postgres: true` and `redis: true`. A 503 means dependencies aren't reachable. On first use Docker will download images. The `pgvector` extension is available in the image, and will be enabled by migrations in the next implementation step.

**Safety:** Do not commit `.env` or `.phase3-fresh.env`. The installer backs up prior backend `.env` locally outside this repository. Do not run `docker compose down -v`—that deletes volume data.

Next steps: SQLAlchemy models + Alembic migrations, then secure auth, job APIs, frontend wiring, security tests, finally GitHub push.
