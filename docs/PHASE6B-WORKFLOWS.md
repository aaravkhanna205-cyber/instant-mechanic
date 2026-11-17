# Phase 6b: Agent workflows (all four agents)

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

## Workflow 3: Interview Summary
Interview completed → Interview Summary agent → review draft → **human decision in Interview Studio**.
1. **Load interview** (only inside your organization).
2. **Check interview finished**: waits (status `waiting_interview`) until the candidate completes it.
3. **Safety scan** of the answers.
4. **Match requirements** against the candidate's own answers, quoting the answer and question number.
5. **Summary**, including questions with no answer or a very short one (under 5 words).
6. **Ask recruiter**: a task reminds you to record the decision in Interview Studio.

The agent never records the hiring decision (advance, hold or reject). Its own tools cannot read resumes.

## Job Description agent
Job → check wording → draft → **recruiter approval**.
- Flags wording that can exclude people (age limits, "male only", "boys", "salesman", marital status, appearance) as **Fix**, and gaps (no salary, hours, responsibilities, location, vague or duplicate requirements) as **Improve**.
- The draft only reorganises the current text; missing facts appear as `[placeholders]`. Nothing is invented.
- The job changes only when a recruiter clicks **Approve and update job description**, and then only its description. Status, title and requirements are never changed; the agent never publishes or closes a job.

## Recruitment Analytics agent
Read-only, finishes immediately as `completed` (nothing to approve).
- Counts for the chosen period (7 to 180 days) against the period before, open applications by stage, applications waiting 7+ days with no stage change, overdue interviews, published jobs with no applicants, and jobs that drove a change in volume.
- Uses one read-only tool that returns counts for your organization only. No candidate names leave it.

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
| `backend/app/ai/agents/workflows/resume_review.py` | Resume Review steps and the shared checkpointed runner, resume, review, cancel |
| `backend/app/ai/agents/workflows/interview_summary.py` | Interview Summary steps and start |
| `backend/app/ai/agents/workflows/job_description.py`, `jd_quality.py` | Job Description agent and its checks and draft |
| `backend/app/ai/agents/workflows/recruitment_analytics.py`, `analytics.py` | Recruitment Analytics agent and its findings |
| `backend/app/ai/agents/workflows/models.py` | `phase6_workflow_runs` table |
| `backend/app/ai/agents/workflows/api.py` | `/api/phase6/organizations/{id}/workflows/...` |
| `backend/alembic/versions/0008_phase6_workflow_runs.py` | Migration: workflow runs table |
| `backend/alembic/versions/0009_phase6_interview_summary.py` | Migration: allows the `waiting_interview` status |
| `backend/alembic/versions/0010_phase6_job_and_analytics_agents.py` | Migration: runs without an application |
| `backend/tests/test_phase6b_workflows.py`, `test_phase6c_interview_summary.py`, `test_phase6d_job_and_analytics.py` | 29 tests |
| `frontend/app/phase6/workflows/page.tsx` | The Agent workflows page (both workflows) |

## Note on LangGraph
The checkpoints are this project's own table rather than LangGraph's PostgreSQL saver. It needs no extra package, works with the existing Alembic migrations and SQLite tests, and keeps each run readable in the database.

## Apply and run (Windows PowerShell, from the project root)
```powershell
cd backend
python -m pytest -q tests/test_phase6b_workflows.py tests/test_phase6c_interview_summary.py tests/test_phase6d_job_and_analytics.py
cd ..
.\scripts\selfhost.ps1
docker exec imhire_phase5_app-api-1 python -m alembic upgrade head
docker exec imhire_phase5_app-api-1 python -m alembic current
```
`alembic current` must show `0010_phase6_job_analytics (head)`. Then open `/phase6/workflows`.
