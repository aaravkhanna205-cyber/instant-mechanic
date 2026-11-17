# Sending real emails from Gmail

Until you do this, emails are only **stored** (outbox mode): staff can see them under
**Notifications > Emails to candidates**, but nobody receives them.

Use a Gmail account made for hiring (for example a new `instantmechanic.hiring@gmail.com`), not a personal one.

## 1. Create a Gmail App Password

1. Sign in to that Gmail account in a browser.
2. Open **https://myaccount.google.com/security** and turn on **2-Step Verification** (Google requires it).
3. Open **https://myaccount.google.com/apppasswords**.
4. Name it `Instant Mechanic Hire` and press **Create**.
5. Google shows **16 letters** in four groups. Keep that window open for the next step.

The App Password is not your normal Gmail password. It only lets this app send email, and you can delete it any time on the same page.

## 2. Put it into the app (on the server PC)

In PowerShell, in the project folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\email-setup.ps1
```

It asks for the Gmail address, then the 16 letters (hidden while you type or paste). They are saved only in
`.env.phase5.local` on this PC, which is never uploaded to GitHub. **Never paste the App Password in a chat or an email.**

## 3. Restart and send a test

```powershell
.\scripts\selfhost.ps1
docker exec imhire_phase5_app-p6-worker-1 python -m app.phase8.test_email YOUR-OWN-EMAIL@gmail.com
```

`PASS` means Gmail accepted it. Check the inbox and the spam folder.

| Message | Meaning |
|---|---|
| Gmail refused the login | Wrong App Password, or 2-Step Verification is off. Create a new App Password and run step 2 again |
| Email mode is outbox | Step 2 was not finished, or the site was not restarted |
| Connection refused / timed out | The PC has no internet, or a firewall blocks port 587 |

## Limits and good habits

- A normal Gmail account sends about **500 emails a day**. That is plenty for hiring.
- If candidates find the emails in spam, ask a few to mark them **Not spam**.
- To switch emails off again: `.\scripts\email-setup.ps1 -Off`, then `.\scripts\selfhost.ps1`.
- To change the password: create a new App Password, run step 2 again, delete the old one in Google.
