# Phase 3 – Authentication and role permissions

## Scope
This milestone adds working FastAPI endpoints under `/api/auth/` and an isolated Next.js test flow at `/auth-live` and `/auth-live/account`. It does **not** replace the Phase 2 demo screens, add public registration, or automatically promote candidates to recruiters.

## Security model
- Argon2id hashes for administrator passwords; no password is stored in plaintext.
- Interactive, first-admin-only bootstrap; the account creator must already have local server access.
- Opaque 48-byte token using a host-only HttpOnly browser cookie, stored only as a SHA-256 hash in Redis. Eight-hour expiry. Logout deletes the Redis record.
- In local HTTP dev: SameSite=Lax and Secure=False. Production: SameSite=None and Secure=True; use HTTPS and restrict `CORS_ORIGINS` to the exact deployed frontend origins. Prefer a same-site reverse proxy when possible.
- Session bearer cookies require HTTPS in production; CSRF token header is required for authenticated mutations (currently logout). All new mutating endpoints must enforce this dependency or an equivalent anti-CSRF check.
- Login JSON content-type and explicit Origin allowlist. Eight bad attempts per account trigger a Redis-backed 15-minute lockout. Redis outage fails closed.
- Platform-admin privileges come from `users.is_platform_admin`; organization recruiter roles come from `organization_memberships`, checked within each organization.
- Session revocation on logout, inactive users denied at each request, no credentials or tokens printed in logs or included in Git.

## Local commands (from existing project root)
1. `cd backend`
2. `.\.venv\Scripts\python.exe -m pip install -r requirements-phase3-auth.txt`
3. `.\.venv\Scripts\python.exe -m pytest -q`
4. `.\.venv\Scripts\python.exe -m scripts.bootstrap_admin --email you@example.com --name "Instant Mechanic Admin"`
5. `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
6. In a second terminal, `cd frontend; npm run typecheck; npx next build --webpack; npm run dev -- --hostname 127.0.0.1 --port 3000`.
7. Open `http://127.0.0.1:3000/auth-live`; use the exact matching origin in backend CORS_ORIGINS. Log in, verify /auth-live/account, sign out, and confirm /api/auth/me returns 401.

If using a different frontend port, include that precise `http://127.0.0.1:PORT` origin in backend's CORS_ORIGINS and restart FastAPI. NEXT_PUBLIC_API_URL should be set to `http://127.0.0.1:8000` for local usage. Do not put credentials in frontend environment variables.

## RBAC manual checks
- `GET /api/auth/admin-check`: platform admins only.
- `GET /api/auth/organizations/{organization_id}/recruiter-check`: platform admin or same-organization owner/admin/recruiter only.
- `GET /api/auth/me`: requires Redis session cookie.
- Logout requires JSON body `{}` and matching `X-CSRF-Token` from `/me`.

## Limitations and next work
- Add organization/job CRUD, transactional audit logs, authorization tests against real PostgreSQL, registration/invitation approval, secret-management integration, and end-to-end browser tests before a production launch.
- The backend uses a single local process. Configure trustworthy reverse proxy and dedicated Redis credentials before deployment.
- Do not claim the existing recruiter dashboard is protected: Phase 2 routes remain demo-only.
