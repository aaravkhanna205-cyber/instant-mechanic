# Known limits

Honest list of what this version does not do, so nobody is surprised.

## Hosting

- The site lives on one PC. When the PC is off, asleep, signed out, or Docker Desktop is closed, the site does not answer.
  Set Windows power settings to never sleep while plugged in.
- A backup on the same disk does not survive a broken disk. Copy `imhire-backups` to a USB drive or another computer weekly.
- Home internet upload speed limits how fast pages load for many people at once. Fine for hiring volumes (tens of candidates a day).
- Tailscale Funnel is free for personal use; check its terms if the company grows.

## Email

- Gmail sends about 500 emails a day per account. Emails can land in spam at first.
- "Sent" means Gmail accepted it, not that the candidate read it. Open tracking is off by default (privacy).
- No SMS or WhatsApp messages. Candidates who do not check email should be phoned for interviews.

## Resumes and AI

- Resumes must be PDF or Word (.docx), up to 8 MB. Scanned photos of paper resumes have no readable text,
  so the resume evidence is empty for them (the person still applies normally).
- The AI looks for matching words and meaning. It can miss skills written differently and does not check whether claims are true.
- The local AI (Ollama) is optional; without it interview questions come from built-in templates.
- AI never ranks, rejects or hires anyone. People decide.

## Product

- English only. No Hindi screens yet.
- One company organization in normal use (the code supports more).
- Interview times are entered in the browser's local time; staff and candidates in other time zones see converted times.
- No calendar sync (Google Calendar / Outlook). Add interviews to your calendar by hand.
- Data-protection rules (India's DPDP Act 2023) are supported by consent, deletion requests and retention clean-up,
  but how long to keep data is a decision for the company, ideally with legal advice.
