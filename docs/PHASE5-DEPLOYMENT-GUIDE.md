# Phase 5-labelled production deployment preparation

**Roadmap clarification:** In the repository's `docs/PHASES.md`, original Phase 5 = Interviews (steps 33–36), while original Phase 8 = Test and deploy. This kit targets the branch named `phase5-production-deployment` and is a deployment-preparation artifact. It does not implement the interview milestone.

## Safety boundaries
- Additive files only; installer refuses overwrite. It does not run Alembic, `docker compose down -v`, Git merge, or cloud deployment.
- The Docker compose rehearsal uses **existing externally configured PostgreSQL and Redis**; no new DB volumes or destructive steps.
- It binds to local loopback ports 18000 (API) and 13000 (web) and does not provide public TLS. Not production Internet hosting.
- Resume files in `/app/private_uploads` are kept in Docker named volume `resume_private_data`. Verify actual app's private upload location before using it. Review storage encryption, retention, backups, and deletion before real user data.
- Embedding/PyTorch packages can make backend image heavy. Server plans must be sized appropriately.
- The first-party app's CORS/session configuration, cookie attributes, CSRF, password reset, origin settings, upload behavior and worker job paths require manual integration tests.

## Installation (Windows PowerShell)
1. Ensure branch `phase5-production-deployment`, clean or reviewed status.
2. Extract ZIP to Downloads, inspect `Install-Phase5.ps1` and `payload`.
3. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$HOME\Downloads\Instant-Mechanic-Phase5-Deployment-Kit\Install-Phase5.ps1"`
4. Run `powershell -File .\scripts\phase5-preflight.ps1 -Full` from repo root.
5. Test existing development stack with `powershell -File .\scripts\phase5-smoke.ps1`.
6. Test production-container rehearsal only after configuring `.env.phase5.local` from `.env.phase5.example`; never commit private files.

## Container rehearsal (requires Docker Desktop and available database)
`Copy-Item .env.phase5.example .env.phase5.local`
Edit `.env.phase5.local` to use your actual database name/user/password and redis URL. `host.docker.internal` points at the Windows host from Docker Desktop Linux containers; do not use it for cloud deployments. Existing Phase 3 services should already publish on 55433/56380.

`docker compose --env-file .env.phase5.local -f compose.phase5-app.yml config --quiet`
`docker compose --env-file .env.phase5.local -f compose.phase5-app.yml build`
`docker compose --env-file .env.phase5.local -f compose.phase5-app.yml up -d api web`
`powershell -File .\scripts\phase5-smoke.ps1 -Api http://127.0.0.1:18000 -Web http://127.0.0.1:13000`

Enable worker **only after** ensuring persistent file handling and queue configuration:
`docker compose --profile worker --env-file .env.phase5.local -f compose.phase5-app.yml up -d worker`

Don't use `docker compose down -v`; it would remove compose-managed volumes, including uploaded files. Do not apply production migrations without a database backup and tested restore.

## Production deployment plan (manual, no invented cloud credentials)
- Configure managed PostgreSQL that supports **pgvector** (verify extension on intended plan), managed Redis and encrypted private document storage. Check residency, retention, pricing, access policy and provider limitations.
- Deploy backend and worker as independent services with long-lived storage or object storage. Set real `DATABASE_URL`, `REDIS_URL`, secure cookie settings and known `CORS_ORIGINS` (must match the deployed frontend exact origin).
- For Next.js, set `NEXT_PUBLIC_API_URL` at build time to the public HTTPS API URL; values are embedded into client bundles. Ensure the project's API helper actually reads this variable. Build again after changing it.
- Use an HTTPS custom domain. For cross-site browser auth, validate cookie SameSite/Secure/Domain, CSRF and credentials in a real browser; an HTTP curl check is insufficient.
- Run migrations using a one-off release job with database backup/restore verified first. Never automatically migrate on each web startup.
- Turn on provider health checks and alarms; watch 5xx rate, queue age, disk and database usage, failed emails and auth errors; redact PII and tokens in logs.
- GitHub Actions is **CI only**. Publish/production deployment stays manually gated until checks and manual approvals pass.

## Human acceptance / go-live gate
- [ ] API ready, DB, Redis, pgvector and migration head checked
- [ ] Pytest, TypeScript, Next build and Docker build all pass
- [ ] Login, refresh, logout and CSRF tested over HTTPS
- [ ] Super Admin/Recruiter/Candidate organization permissions tested, including negative cases
- [ ] Interview consent captured before interview actions (original Phase 5 scope)
- [ ] Candidate PDF/DOCX uploaded safely, private storage verified, worker completes and recruiter evidence appears
- [ ] Malware scanning, file-size limits, retention/deletion, backups and restore verified
- [ ] No automated rejection or autonomous external actions without human approval
- [ ] Cross-origin browser session tested with production domains
- [ ] Restore drill, monitoring and rollback rehearsed
- [ ] Approved security review and legal/privacy requirements for candidate data

## Git review and push
`git add backend/Dockerfile.phase5 backend/Dockerfile.phase5.dockerignore frontend/Dockerfile.phase5 frontend/Dockerfile.phase5.dockerignore compose.phase5-app.yml .env.phase5.example .github/workflows/phase5-quality.yml scripts/phase5-preflight.ps1 scripts/phase5-smoke.ps1 scripts/phase5-git-review.ps1 docs/PHASE5-DEPLOYMENT-GUIDE.md .gitignore`
`powershell -File .\scripts\phase5-git-review.ps1`
`git --no-pager diff --cached`
`git commit -m "chore: add Phase 5 deployment preparation and CI"`
`git push -u origin phase5-production-deployment`

**Status:** Package contents undergo syntax/structural checks here, not actual Windows installation, Docker image build, cloud provisioning or production end-to-end tests. The project is not deployed merely by installing this kit.
