# Phase 8: release readiness

## What changed

| Area | Change |
|---|---|
| Resume rule | Candidates must upload a resume before applying (the server refuses otherwise). Setting `REQUIRE_RESUME_TO_APPLY=YES` (default). A resume that failed to read does not count |
| Gmail | `scripts/email-setup.ps1` saves a Gmail App Password into `.env.phase5.local` only; `python -m app.phase8.test_email` sends a test. Guide: GMAIL-SETUP.md |
| Error log | Server errors (5xx) are recorded without personal data and shown in **Super Admin > System health > Server errors** (last 24 hours, 7 days, top 10). Migration `0012_phase8_server_errors` |
| Migrations | 0011 and 0012 now also work on a brand-new database (not only on upgrades) |
| Security tests | `backend/tests/test_phase8_release.py` (18 checks) |
| Browser tests | `frontend/e2e` with Playwright (`npm run e2e`) |
| CI | `.github/workflows/ci.yml`: secret scan, backend on PostgreSQL, migrations, frontend lint/type check/build, dependency audit, browser tests |
| Windows | `scripts/windows-tasks.ps1` (start after sign-in + daily backup), `scripts/restore-test.ps1`, backups keep the newest 14, database restarts by itself |
| Verify | `selfhost.ps1 -Verify` checks the Phase 8 database update and says whether real emails are on |
| Lint | The two old lint problems are fixed, so `npm run lint` is clean |
| Docs | README, architecture, Windows setup, Gmail, HR manager, hiring manager, candidate guide, testing, known limits, case study |

## Upgrade steps (on the server PC)

1. Backup: `.\scripts\selfhost.ps1 -Backup`
2. Apply the update (git), then rebuild: `.\scripts\selfhost.ps1`
3. Database update: `docker exec imhire_phase5_app-api-1 python -m alembic upgrade head` (to 0012)
4. Database auto-restart: `docker compose --env-file .phase3-fresh.env -f compose.phase3-fresh.yml up -d`
5. Check: `.\scripts\selfhost.ps1 -Verify`
6. Optional: Gmail (`.\scripts\email-setup.ps1`), automatic start and backup (`.\scripts\windows-tasks.ps1 -Install`), `.\scripts\restore-test.ps1`

To switch the resume rule off, add `REQUIRE_RESUME_TO_APPLY=NO` to `.env.phase5.local` and restart.
