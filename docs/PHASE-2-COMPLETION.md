# Phase 2 completion extension — Instant Mechanic Hire

## Included
- Drag-and-drop recruiter Kanban stages including Trade test; fallback accessible stage dropdown; human audit entry for each stage change.
- Candidate Portal jobs, email-filtered local application tracker, local interview list, resume filename validation (PDF/DOCX up to 5 MB).
- Text-only practice interview: consent gate, four questions, answer navigation, reviewer notes, demo completion. No recording, voice, emails or real bookings.
- Super Admin preview: brand switch, demo CSV import with header validation and invalid-row report, undo last demo batch, filtered audit history.

## Explicit limitations
The Phase 2 data store is localStorage and includes illustrative candidate information. The candidate tracker is *not authenticated*: email matching is not a privacy control. Never enter real candidate data. Files are not uploaded, stored, or parsed. Browser refresh resets in-progress interview answers. CSV imports only metadata, do not import xlsx; backend and storage arrive in later phases. No AI decision or automated hiring occurs.

## Manual acceptance checks
1. Visit `/jobs/job-101` and drag a demo applicant from Trade test to Interview. Confirm the dropdown and audit change.
2. Visit `/portal`, apply with a dummy email and PDF/DOCX filename. Confirm invalid extensions are refused and that the tracker only shows the email-filtered demo records.
3. Visit `/interviews` and open an existing session on `/interviews/int-101`. Confirm consent is required, answer navigation works, human notes and completion operate.
4. Visit `/admin` and import a dummy CSV with `name,email,phone` headers, include an invalid email; verify row errors, valid metadata, and undo.
5. Check 375px and 768px widths, both themes, and keyboard navigation.
6. Run `npm run lint`, `npm run typecheck`, `npx next build --webpack`.

## Git
Commit only after checks: `git add frontend docs/PHASE-2-COMPLETION.md; git commit -m "feat: finish Phase 2 demo workflows"; git push origin main`.
