# Phase 4 — AI assistance (human-reviewed)

This package integrates with the Phase 3 authentication, recruitment, application and organization model.

## Included
- Candidate-only (authenticated, own-account) PDF/DOCX upload, size/type checks, explicit consent, private local storage, deletion.
- Redis-backed background worker and local sentence-transformer embeddings (384 dims).
- Postgres/pgvector excerpt retrieval for a **single selected application**. No automated candidate ranking or rejection.
- Reviewable skills with direct resume evidence, rule-based interview prompts and human review notes.
- Two Next.js pages: `/phase4` and `/phase4/resume`.
- Alembic revision `0004_phase4_ai`, verification script and unit tests.

## Security limitations before production
- Local disk storage is development-only. Use encrypted private object storage with access logging, lifecycle deletion and backups in production.
- Add malware scanner in the upload pipeline and fail closed until scans succeed. Do **not** expose the resume upload endpoint publicly without this control.
- Extracted resume text and vector excerpts are personal data. Implement retention periods, deletion audit, data subject access, and access monitoring.
- Run file parsing and embedding inference in a resource-limited isolated worker/container. DOCX and PDF parsers should not run with elevated privileges.
- A candidate's upload remains accessible to a recruiter only through an existing application to the recruiter's own organization.
- Do not use protected attributes, automated rankings, or AI-only hiring decisions.
- LLM free-form interview generation, SMTP notifications, provider cost controls, model evaluations and deployment infrastructure are **not** provided by this package.

## Local procedure
1. Run installer from repo root on `phase4-ai-recruitment`.
2. `cd backend` and `./.venv/Scripts/python.exe -m pip install -r requirements-phase4-complete.txt`.
3. `./.venv/Scripts/python.exe -m pytest -q`.
4. `./.venv/Scripts/python.exe -m alembic upgrade head`.
5. `./.venv/Scripts/python.exe -m scripts.verify_phase4`.
6. Start FastAPI, Next.js, and a third terminal: `./.venv/Scripts/python.exe -m app.phase4_ai.worker`.
7. Candidate uploads through `/phase4/resume`; authorized recruiters view evidence at `/phase4`.
8. Verify authorization boundaries, denial of unconsented uploads, deletion, job matching, human-review persistence and Git status.

The model downloads on first processing; it may require network access and substantial disk space.
