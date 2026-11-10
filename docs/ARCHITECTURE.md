# Target architecture — implementation is progressive

```
Browser → Next.js app (Vercel when deployed)
               ↓ HTTPS + auth session
          FastAPI (Render when deployed)
            ├─ Services / repositories → PostgreSQL + pgvector (Neon)
            ├─ Background work / rate limiting → Redis (managed service)
            ├─ Resume private object storage (provider TBD)
            └─ AI layer / LangGraph → LLM provider (server-side keys)
```

The frontend has a recruiter workspace, candidate portal and super admin area. Target 22 tables in six groups: identity (6), hiring (5), interviews (4), AI/messaging (2), trust (3), administration (2). Not yet created. Use Alembic migrations in Phase 3. The current backend exposes only `/api/health`; nothing else can be assumed to exist.

- Theme: yellow #FBBF24, orange #F97316, deep orange #C2410C, background #FFFCF7.
- Keys: keep in untracked `.env` locally; set via Render/Vercel/Neon/Redis consoles on deployment. Never bundle actual keys or use NEXT_PUBLIC_ for secrets.
- Frontend on Vercel may require plan suitable for organization/company use; confirm terms and current pricing before deployment.
- Redis managed hosting, object storage, monitoring, and hosted AI may cost money.
