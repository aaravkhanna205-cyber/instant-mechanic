# Phase 6b: Resume Review workflow

Workflow 1 of the roadmap: **new resume → Resume Analysis agent → evidence matrix → recruiter review**.
Free: no paid AI key, no LLM. It reuses the resume text that Phase 4 already extracted.

## What it does
1. **Load application**: job and candidate, only inside your organization.
2. **Check resume**: waits (status `waiting_resume`) if the candidate has no processed resume yet.
3. **Safety scan**: resume lines that look like instructions to an AI ("ignore previous instructions", "hire this candidate") are set aside and shown to the recruiter. They are never used as evidence.
4. **Match requirements**: for every job requirement: *Text found*, *Needs checking* or *No text found*, with the exact resume quote.
5. **Summary**: counts and requirement names only. Not a score, ranking or recommendation.
6. **Ask recruiter**: status `waiting_review`, plus a task in the Phase 6 Tasks list.

The recruiter confirms or corrects each requirement and writes a note. The application stage is never changed and the candidate is never messaged.

## Safety built in
| Roadmap item | How |
|---|---|
| Checkpoints | Each step's result is saved in `phase6_workflow_runs`. **Resume run** continues after the last saved step; finished steps are not repeated. |
| Restart in the middle | A run left `running` (server stopped) can be resumed after 2 minutes. |
| Tool allowlist | `tools.ALLOWLIST`: the Resume Analysis agent may use only 4 tools. Any other tool is refused and logged. |
| Permission inside every tool | Each tool re-checks that the user is an active recruiter of this organization and the record belongs to it. |
| Failure recovery | A failing step marks the run `failed` with the reason. Up to 5 attempts, then start a new run. |
| Audit | Every step, tool call, refusal, wait, failure and review goes to `phase6_events`. |

## Files
| Path | Purpose |
|---|---|
| `backend/app/ai/agents/workflows/evidence.py` | Matching, safety scan, summary (pure functions) |
| `backend/app/ai/agents/workflows/tools.py` | Tools, allowlist, permission checks |
| `backend/app/ai/agents/workflows/resume_review.py` | Steps, checkpointed runner, resume, review, cancel |
| `backend/app/ai/agents/workflows/models.py` | `phase6_workflow_runs` table |
| `backend/app/ai/agents/workflows/api.py` | `/api/phase6/organizations/{id}/workflows/...` |
| `backend/alembic/versions/0008_phase6_workflow_runs.py` | Migration |
| `backend/tests/test_phase6b_workflows.py` | 13 tests |
| `frontend/app/phase6/workflows/page.tsx` | The Resume Review page |

## Note on LangGraph
The checkpoints are this project's own table rather than LangGraph's PostgreSQL saver. It needs no extra package, works with the existing Alembic migrations and SQLite tests, and keeps each run readable in the database.

## Apply and run (Windows PowerShell, from the project root)
```powershell
cd backend
python -m pytest -q tests/test_phase6b_workflows.py
cd ..
.\scripts\selfhost.ps1
docker exec imhire_phase5_app-api-1 python -m alembic upgrade head
docker exec imhire_phase5_app-api-1 python -m alembic current
```
`alembic current` must show `0008_phase6_workflow_runs (head)`. Then open `/phase6/workflows`.
