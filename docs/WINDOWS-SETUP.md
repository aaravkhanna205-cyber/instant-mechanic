# Running Instant Mechanic Hire on the Windows PC

All commands are for **PowerShell**, run **inside the project folder** (the folder with `README.md`).
Lines starting with `#` are notes; do not type them.

## What the PC needs (all free)

| Program | Why |
|---|---|
| Docker Desktop | Runs the database, the app and the virus scanner |
| Git | Gets updates of the code |
| Tailscale | Gives the site a fixed public HTTPS address (Funnel) |
| Ollama (optional) | Local AI for interview question drafts. Without it, simple built-in drafts are used |

The PC must be **on, signed in, with Docker Desktop running** for the site to answer.

## 1. Start the database (first time only)

```powershell
docker compose --env-file .phase3-fresh.env -f compose.phase3-fresh.yml up -d
```

## 2. Start the site

First time (use your own Tailscale address):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\selfhost.ps1 -PublicUrl https://YOUR-PC.YOUR-TAILNET.ts.net
```

Every later time: `.\scripts\selfhost.ps1`

Make the address public once: `tailscale funnel --bg 13080`

## 3. Update the database after a code update

```powershell
docker exec imhire_phase5_app-api-1 python -m alembic upgrade head
```

## 4. Check everything

```powershell
.\scripts\selfhost.ps1 -Verify
```

All lines should say PASS. It also tells you whether real emails are on.

## 5. Automatic start and daily backup (do once)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows-tasks.ps1 -Install
```

- The site starts by itself about 2 minutes after you sign in to Windows.
- A backup runs every day at 13:30 (or as soon as the PC is on after that). The newest 14 are kept in `C:\Users\<you>\imhire-backups`.
- Logs are in `C:\Users\<you>\imhire-logs`.
- In **Docker Desktop > Settings > General**, tick **Start Docker Desktop when you sign in**.
- Check the tasks any time: `.\scripts\windows-tasks.ps1 -Status`. Remove them: `-Remove`.
- Choose another backup time: `.\scripts\windows-tasks.ps1 -Install -BackupTime 21:00`

## 6. Backups

- Backup now: `.\scripts\selfhost.ps1 -Backup`
- Prove a backup can be restored (does not touch the live data): `.\scripts\restore-test.ps1`
- Once a week, copy the `imhire-backups` folder to a USB drive or another disk. A backup on the same PC does not help if the PC breaks.

## 7. Real emails from Gmail

See [GMAIL-SETUP.md](GMAIL-SETUP.md). Short version: `.\scripts\email-setup.ps1`, then `.\scripts\selfhost.ps1`.

## 8. Stop the site

`.\scripts\selfhost.ps1 -Stop`

## When something is wrong

| You see | Do this |
|---|---|
| "Docker is not running" | Open Docker Desktop, wait until it says running, run the command again |
| The API did not become ready | Start the database (step 1), then `.\scripts\selfhost.ps1` again |
| Timeout on port 55433 | Same as above: database not running |
| 401 on a page | You are not signed in on that address. Sign in at the public address |
| Site works on the PC but not on phones | `tailscale funnel --bg 13080` and check Tailscale is connected |
| Errors in System health (Super Admin) | The table shows which page fails; send it to whoever maintains the code |
