# Testing

## Backend tests (about 135, a few seconds)

```powershell
cd backend
python -m pytest -q
```

They use a throwaway SQLite database and an in-memory Redis, so they never touch real data.
`tests/test_phase8_release.py` covers the release checks: resume-before-apply rule, every staff page refused
to candidates, no access across organizations, cookie flags, login lock after 8 wrong passwords, CSRF and
origin checks, bad / fake / empty / oversize uploads, the server-error log and the repository secret scan.

Run the Phase 7 tests on real PostgreSQL (use an EMPTY test database, it is wiped):

```powershell
$env:PHASE7_TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASS@127.0.0.1:55433/imhire_test'
python -m pytest -q tests/test_phase7_enterprise.py
```

## Browser tests (Playwright)

`frontend/e2e/hiring-flow.spec.ts` drives a real browser through the whole story:
a candidate registers, is asked for a resume, uploads one and applies; the hiring manager shortlists and
schedules an interview; the candidate confirms; the HR manager sees the candidate emails.
`frontend/e2e/phone.spec.ts` checks the public pages fit a phone screen.

They need a running API on port 8000 with a **separate test database** (never the real one):

```powershell
# backend, in a second PowerShell window
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASS@127.0.0.1:55433/imhire_e2e'   # an empty database named *e2e*
$env:REDIS_URL = 'redis://127.0.0.1:56380/5'
$env:E2E_SEED = 'YES'; $env:E2E_PASSWORD = 'any-12-char-password'
python -m alembic upgrade head
python -m scripts.e2e_seed
python -m uvicorn app.main:app --port 8000

# frontend, in a third window
npm run build; npx next start -p 3000
$env:E2E_PASSWORD = 'any-12-char-password'
npx playwright install chromium   # first time only
npm run e2e
```

The seed script refuses to run unless the database name contains "e2e" or "test".

## Secret scan

```powershell
python scripts/secret_scan.py
```

Fails if a password, API key, private key or a private settings file (`.env.phase5.local`, `.phase3-fresh.env`) is committed.

## GitHub CI

`.github/workflows/ci.yml` runs on every push: secret scan; backend tests on PostgreSQL with pgvector and
migrations up / down / up; frontend type check, lint and build; dependency audit (advisory, never blocks);
then the browser tests against a fresh database.
