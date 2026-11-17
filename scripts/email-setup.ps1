# Switch candidate and agent emails on (Gmail) or back off (outbox = stored only).
#   On:   powershell -ExecutionPolicy Bypass -File .\scripts\email-setup.ps1
#   Off:  powershell -ExecutionPolicy Bypass -File .\scripts\email-setup.ps1 -Off
# Your Gmail App Password is written only to .env.phase5.local on this PC (never committed).
param([switch]$Off)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$envFile = Join-Path $root '.env.phase5.local'
if (-not (Test-Path $envFile)) { throw '.env.phase5.local not found. Run this from the project folder.' }

function Set-EnvValue([string]$Key, [string]$Value) {
  $lines = @(Get-Content $envFile)
  $found = $false
  $lines = $lines | ForEach-Object {
    if ($_ -match "^$([regex]::Escape($Key))=") { $found = $true; "$Key=$Value" } else { $_ }
  }
  if (-not $found) { $lines += "$Key=$Value" }
  Set-Content -Path $envFile -Value $lines -Encoding ascii
}

if ($Off) {
  Set-EnvValue 'PHASE6_DELIVERY_MODE' 'outbox'
  Set-EnvValue 'PHASE6_SMTP_ENABLED' 'NO'
  Write-Host 'Emails switched OFF (outbox mode). Restart the site: .\scripts\selfhost.ps1' -ForegroundColor Yellow
  exit 0
}

Write-Host ''
Write-Host 'Gmail setup' -ForegroundColor Cyan
Write-Host '1. Turn on 2-Step Verification for the Gmail account.'
Write-Host '2. Open https://myaccount.google.com/apppasswords, create an app password named "Instant Mechanic Hire".'
Write-Host '3. Google shows 16 letters. Paste them below (spaces are fine).'
Write-Host ''
$address = (Read-Host 'Gmail address that sends the emails').Trim()
if ($address -notmatch '^[^@\s]+@[^@\s]+\.[^@\s]+$') { throw 'That does not look like an email address.' }
$secure = Read-Host 'App password (16 letters, hidden)' -AsSecureString
$plain = [System.Net.NetworkCredential]::new('', $secure).Password
# Google App Passwords are 16 letters a-z. Copying from the Google page can add spaces, dashes or
# invisible characters, so keep only the letters.
$plain = ($plain -replace '[^a-zA-Z]', '').ToLower()
if ($plain.Length -ne 16) {
  throw "Found $($plain.Length) letters, but an App Password has exactly 16. Paste only the 16 letters Google showed (spaces are fine) and run this again."
}

Set-EnvValue 'PHASE6_DELIVERY_MODE' 'smtp'
Set-EnvValue 'PHASE6_SMTP_ENABLED' 'YES'
Set-EnvValue 'PHASE6_SMTP_HOST' 'smtp.gmail.com'
Set-EnvValue 'PHASE6_SMTP_PORT' '587'
Set-EnvValue 'PHASE6_SMTP_USER' $address
Set-EnvValue 'PHASE6_SMTP_PASSWORD' $plain
Set-EnvValue 'PHASE6_SMTP_FROM' $address
$plain = $null

Write-Host ''
Write-Host 'Saved to .env.phase5.local (private, not in Git).' -ForegroundColor Green
Write-Host 'Next:'
Write-Host '  1. Restart the site:   .\scripts\selfhost.ps1'
Write-Host "  2. Send a test email:  docker exec imhire_phase5_app-p6-worker-1 python -m app.phase8.test_email $address"
Write-Host 'Gmail sends up to about 500 emails a day from a normal account.'
