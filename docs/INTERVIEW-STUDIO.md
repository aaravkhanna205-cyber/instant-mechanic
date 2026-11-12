# Interview Studio (roadmap steps 33-36)

Pages
- Recruiter: `/interview-studio` - reschedule or cancel, draft and approve questions, read answers, record a decision.
- Candidate: `/interview-studio/session` - confirm or decline, give consent, answer one question at a time.

How an interview runs
1. A recruiter schedules the interview on the existing Interviews page.
2. In Interview Studio the recruiter asks for draft questions, edits them, and approves them. Only approved questions are saved.
3. The candidate confirms, gives consent, and answers. Each answer is saved before the next question appears, so a lost
   connection resumes at the same question.
4. The recruiter reads the answers and records advance, hold or reject with a reason.

Rules the server enforces
- No question reaches a candidate without recruiter approval.
- No session without the candidate's recorded consent for that interview; withdrawing consent stops the session.
- Questions about age, family, religion, caste, gender, health, nationality or politics are rejected.
- The report has no score and no recommendation. The decision is typed by a person and changes no application stage.

Question drafts
- Built-in rules by default (free, instant).
- Optional local AI: install Ollama on the PC, run `ollama pull llama3.2:3b`, and set `OLLAMA_URL`.
  - Development (`backend\.env`): `OLLAMA_URL=http://127.0.0.1:11434`
  - Self-hosting (`scripts\selfhost.ps1`): already points at Ollama on this PC.
  - If Ollama is off or slow, drafting falls back to the rules automatically.
- This is prompt-guided drafting, not a fine-tuned model.

Reminders
- `python -m scripts.send_interview_reminders` creates in-app reminders for interviews in the next 24 hours.
  Run it on a schedule (for example Windows Task Scheduler, hourly). Email is not sent.

Not included
- Voice answers (marked optional in the roadmap).
- Email or calendar invitations.
