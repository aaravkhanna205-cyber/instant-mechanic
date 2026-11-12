# Production hosting on one server

This runs the whole app on a single Ubuntu server with Docker:
Caddy (HTTPS) -> Next.js and FastAPI, plus the resume worker, PostgreSQL
(pgvector), Redis and ClamAV. Only ports 80 and 443 are open to the internet.

## Before you start
- A server with Ubuntu 24.04 and at least 8 GB RAM (the AI model and the malware
  scanner each need over 1 GB).
- A domain whose DNS A record points at the server's IP address.

## First deployment (run on the server as root)
```bash
git clone https://github.com/aaravkhanna205-cyber/instant-mechanic.git /opt/instant-mechanic
cd /opt/instant-mechanic
bash scripts/prod-server-setup.sh
cp .env.prod.example .env.prod
nano .env.prod            # set DOMAIN, ACME_EMAIL, POSTGRES_PASSWORD (openssl rand -hex 24)
bash scripts/prod-deploy.sh
docker compose --env-file .env.prod -f compose.prod.yml exec api \
  python -m scripts.bootstrap_admin --email YOUR_EMAIL --name "YOUR NAME"
bash scripts/prod-backup.sh
bash scripts/prod-restore-test.sh
bash scripts/prod-verify.sh
```

## Updating later
```bash
cd /opt/instant-mechanic && git pull && bash scripts/prod-deploy.sh
```
`prod-deploy.sh` backs up the database before it applies migrations.

## What the scripts do
| Script | Purpose |
|---|---|
| `prod-server-setup.sh` | Docker, firewall, automatic security updates, swap, nightly backup job |
| `prod-deploy.sh` | Build, migrate, start, wait for HTTPS |
| `prod-backup.sh` | Database dump and resume archive in `/opt/imhire-backups`, 14 days kept |
| `prod-restore-test.sh` | Restores the newest backup into a throwaway database to prove it works |
| `prod-verify.sh` | HTTPS, headers, access control, closed ports, malware scanner, schema |

## Security notes
- Resume uploads are scanned by ClamAV before they are saved. If the scanner is
  down, uploads are refused rather than accepted unscanned.
- Resumes are stored in the private Docker volume `resume_private_data`, never
  under a public web path.
- Never run `docker compose down -v`: it deletes the database and the resumes.
- Backups live on the same server. Also enable the hosting provider's server
  backups, or copy `/opt/imhire-backups` elsewhere, so a lost server is recoverable.
- Password-reset email stays off until the SMTP settings in `.env.prod` are filled in.

## Manual go-live checks (in a browser, on the real domain)
- [ ] Sign in, refresh the page, sign out
- [ ] Candidate uploads a PDF and it reaches `ready`
- [ ] Recruiter sees evidence only for applications in their own organization
- [ ] A candidate account cannot open the recruiter or admin pages
- [ ] Privacy notice, data-retention period and deletion process agreed for candidate data
