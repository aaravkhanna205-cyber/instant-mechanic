# Instant Mechanic Hire - Phase 6 guide (AI agents, human-approved)

## What Phase 6 adds
- **Agent Planner**: drafts a candidate message (interview reminder, interview invitation, application follow-up, document request) from a real interview or application.
- **Approval Queue**: every draft waits as `pending`. A recruiter edits, approves or rejects it. Nothing leaves without approval plus a separate "Queue" click.
- **Scheduler**: every 5 minutes it drafts reminders for interviews in the next 24 hours and follow-ups for applications older than 3 days. Drafts only.
- **Worker**: handles queued, approved messages. Default mode is `outbox`: saved in the database, **no email is sent**.
- **Tasks**, **Knowledge search** (returns matching extracts of policies you pasted, nothing invented), **Interview helper**, **Audit log**, and the **/phase6 dashboard**.
- Free by default: no paid AI key. Optional local Ollama can reword drafts.
- It never makes or sends a hiring decision. Drafts containing words such as "reject", "you are hired", "fired", "disqualify", "blacklist" or "withdraw" are refused.

## Files
| Path | Purpose |
|---|---|
| `backend/app/phase6_agents/policy.py` | Message templates, blocked-word check, knowledge search |
| `backend/app/phase6_agents/graph.py` | LangGraph flow: plan -> draft -> policy -> approval_required |
| `backend/app/phase6_agents/local_llm.py` | Optional Ollama rewording (off by default) |
| `backend/app/phase6_agents/models.py` | 5 tables: proposals, events, knowledge, tasks, deliveries |
| `backend/app/phase6_agents/service.py` | Create a proposal, approve / reject / cancel |
| `backend/app/phase6_agents/api.py` | All `/api/phase6/organizations/{id}/...` endpoints |
| `backend/app/phase6_agents/scheduler.py` | Background scanner (drafts only) |
| `backend/app/phase6_agents/worker.py` | Background delivery (outbox or SMTP) |
| `backend/alembic/versions/0006_phase6_agents.py` | Database migration |
| `backend/scripts/phase6_register.py` | Adds the Phase 6 router to `app/main.py` (backs it up first) |
| `backend/scripts/verify_phase6.py` | Prints `PHASE 6 READY` when tables, migration and Redis are fine |
| `backend/tests/test_phase6_full.py`, `test_phase6_http.py` | 18 tests |
| `frontend/app/phase6/page.tsx` | Dashboard page |
| `scripts/phase6/*.ps1` | Start the workers; verify and push |
| `.github/workflows/phase6-tests.yml` | GitHub checks |

## Steps
All commands run in the VS Code PowerShell terminal. `REPO` means your project root (the folder that contains `backend` and `frontend`).

**1. Check, then install the files** (from `REPO`)
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\Downloads\Apply-Phase6.ps1" -CheckOnly
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\Downloads\Apply-Phase6.ps1"
```
The first command only checks and changes nothing. The second asks you to type `YES`, switches to the branch `phase6-agentic-automation`, writes the files and registers the API in `main.py`.

**2. Install the one new package and run the tests**
```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-phase6.txt
.\.venv\Scripts\python.exe -m pytest -q tests/test_phase6_full.py tests/test_phase6_http.py
.\.venv\Scripts\python.exe -m pytest -q
```
Expect `18 passed` on the second command.

**3. Back up the database, then migrate**
Back up first, with whichever matches how your PostgreSQL runs:
```powershell
docker exec <postgres-container> pg_dump -U <db-user> <db-name> > "$HOME\phase6-backup.sql"
pg_dump "<your DATABASE_URL>" > "$HOME\phase6-backup.sql"
```
Then:
```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.verify_phase6
```
`alembic current` must show `0005_interview_studio` before the upgrade. The last command must print `PHASE 6 READY`.

**4. Restart the app**
Stop and start the backend (one copy only), start the frontend, open `http://127.0.0.1:3000/phase6`.

**5. Start the scheduler and the worker** (from `REPO`)
```powershell
.\scripts\phase6\Start-Phase6-Workers.ps1
```
Two windows open and keep running. That is normal.

**6. Browser walk-through with a test candidate**
1. Agent Planner: choose an action, paste an interview or application ID, click Generate.
2. Approval Queue: edit the draft, Approve, then Queue approved action.
3. Activity & Delivery: within a few seconds the delivery shows `outbox`.
4. Sign in as a candidate and open `/phase6`: it must show an error and no data.

**7. Verify and push** (from `REPO`)
```powershell
.\scripts\phase6\Verify-And-Push-Phase6.ps1
.\scripts\phase6\Verify-And-Push-Phase6.ps1 -Push
```
The first runs all checks only. The second commits and pushes the Phase 6 branch after you type `PUSH-PHASE6`.

## Settings (put in `backend/.env`, never commit real values)
See `backend/.env.phase6.example`.
- `PHASE6_DELIVERY_MODE=outbox` (default, sends nothing) or `smtp`
- Real email needs `PHASE6_DELIVERY_MODE=smtp`, `PHASE6_SMTP_ENABLED=YES`, plus host, port (465 or 587), user, password and from-address.
- Local AI rewording: install Ollama, `ollama pull gemma3:1b`, then `PHASE6_ENABLE_LOCAL_LLM=YES`. If Ollama is not running, the plain template is used.

## Troubleshooting
- **Check reports a missing module or column**: your project names it differently from what Phase 6 expects. Do not install; fix the import in the listed Phase 6 file first.
- **"Working tree is not clean"**: commit or stash your own changes first.
- **"A different file already exists"**: Phase 6 was partly installed before. Compare with `git diff` instead of overwriting.
- **Migration error**: check `alembic current`. Never delete database volumes or stamp revisions to get past it.
- **No email arrives**: expected in outbox mode.
- **A delivery shows `failed`**: it is never retried automatically, to avoid double emails. Check, then use the retry endpoint.
- **Dashboard says unauthorized**: sign in as a recruiter or admin who belongs to the organization.
- **To undo before migrating**: `git switch <your old branch>` then `git branch -D phase6-agentic-automation`. A copy of the original `main.py` is in `%USERPROFILE%\InstantMechanicPhase6Backups`.
