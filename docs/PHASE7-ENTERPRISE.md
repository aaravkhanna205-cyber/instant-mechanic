# Phase 7: Team, roles, notifications, reports and data rules

## Roles at Instant Mechanic
| Person | Role | What they can do |
|---|---|---|
| Aarav Khanna | Super Admin + Hiring manager | Everything, in every organization. Interviews, shortlisting, hiring decisions. |
| Neeraj | HR manager | Everything in Instant Mechanic: jobs, candidates, interviews, decisions, team, emails, reports, exports. |
| Trainers, helpers | Recruiter or Interviewer | Recruiter: jobs, candidates, interviews, agents (no team or exports). Interviewer: interviews and feedback. |
| Applicants | Candidate | The candidate portal only. |

Super Admin is a switch on the account (Super Admin → People and roles → **Make Super Admin**), not a role.
Owner, organization admin, HR manager and hiring manager all have **full access** to their organization.
Safety rules: nobody changes their own role; the last person with full access cannot be removed or downgraded;
there is always at least one Super Admin.

The role lists live in one file: `backend/app/security/roles.py` (frontend copy: `FULL_ACCESS_ROLES` in `frontend/lib/api/phase3.ts`).

## What is new
| Page | What it does |
|---|---|
| **Team and roles** (`/team`) | Full-access people add, change and remove team members. |
| **Notifications** (`/notifications`, bell in the header) | Your updates. Full-access people also see **Emails to candidates** with send status. |
| **Reports** (`/reports`) | New applications, open jobs, time to hire, interview completion, hiring funnel with drop-off, conversion, per-job table, team activity. Print or save as PDF. **Find applications** with search, filters, pages and CSV downloads. |
| **Super Admin → System health** | Database, Redis, waiting and failed emails, resumes, agent messages, workflows, deletion requests. |
| **Super Admin → Data retention** | Finds candidates whose applications are all closed with no activity for 6 months to 3 years; deletes them after you type the number to confirm. |
| **Candidate portal** | Next-steps checklist, resume upload inside the portal, interview cards with "I will attend / I cannot attend", plain-language stage explanations, notifications. |

## Emails to candidates
Sent when a candidate applies, changes stage, or has an interview scheduled, moved or cancelled.
They use the same setting as the Phase 6 agent messages:
- `PHASE6_DELIVERY_MODE=outbox` (default): stored and shown as "Stored (outbox mode)". **Nothing is sent.**
- `PHASE6_DELIVERY_MODE=smtp` with `PHASE6_SMTP_ENABLED=YES` and the SMTP settings: really sent.
Links in emails use `PUBLIC_URL` (already set for self-hosting).

## Other changes
- Approved data-deletion requests now also delete the resume files from disk (before, the database rows went but files stayed).
- CSV exports protect against spreadsheet formula injection, include a BOM so Excel shows Hindi names correctly, are limited to full-access roles and are written to the audit log.
- The old "Agents" and "Approvals" placeholder pages now open the live Phase 6 pages.

## Database
Migration `0011_phase7_enterprise`: adds the `hr_manager` and `hiring_manager` roles and the notification fields
`organization_id`, `link`, `email_status`, `emailed_at`, `email_error`. Downgrading turns those two roles into `admin`.

## Tests
`backend/tests/test_phase7_enterprise.py` (14 tests): role access for every role and another company,
team rules, notifications and emails, failed email, deletion-request alert, search and pages, report numbers,
safe and scoped CSV, Super Admin switch rules, retention. They also run on PostgreSQL:
`$env:PHASE7_TEST_DATABASE_URL="postgresql+psycopg://user:pass@127.0.0.1:55433/throwaway_db"` (the database is wiped).
