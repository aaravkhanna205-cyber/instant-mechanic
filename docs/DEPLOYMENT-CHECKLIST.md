# Deployment preparation (Phase 8, not executed)

1. Confirm account terms and costs (commercial Vercel use, Render uptime, Neon storage, managed Redis, private object storage).
2. Connect **one** GitHub repo, with Vercel root `frontend`, Render source root `backend`.
3. Store DATABASE_URL, REDIS_URL, SESSION_SECRET, and LLM_API_KEY as managed backend secrets only. Never expose on frontend.
4. Configure allowed frontend origin on backend, HTTPS, cookie security, roles, cross-organization tests, and safe private upload storage.
5. Run migrations, backend/frontend tests, security checks, backup/restore verification.
6. Only then enable public traffic. Current starter should NOT be deployed as a functioning recruitment site.
