# Started by the Windows task "InstantMechanicHire-Start" when you sign in to this PC.
# Waits for Docker Desktop, starts the database and Redis, then the website. Log: $HOME\imhire-logs\startup.log
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$logDir = Join-Path $HOME 'imhire-logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path (Join-Path $logDir 'startup.log') -Append | Out-Null
try {
  Write-Host "$(Get-Date -Format s) starting Instant Mechanic Hire"
  $ready = $false
  for ($i = 0; $i -lt 60 -and -not $ready; $i++) {   # up to 10 minutes
    cmd /c "docker info >nul 2>&1"
    if ($LASTEXITCODE -eq 0) { $ready = $true } else { Start-Sleep -Seconds 10 }
  }
  if (-not $ready) { throw 'Docker Desktop did not start within 10 minutes. Open it and run scripts\selfhost.ps1.' }
  if (Test-Path '.phase3-fresh.env') {
    & docker compose --env-file .phase3-fresh.env -f compose.phase3-fresh.yml up -d
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the database.' }
    Start-Sleep -Seconds 10
  }
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'selfhost.ps1')
  if ($LASTEXITCODE -ne 0) { throw 'selfhost.ps1 reported a problem (see above).' }
  Write-Host "$(Get-Date -Format s) site is up"
} catch {
  Write-Host "$(Get-Date -Format s) FAILED: $($_.Exception.Message)"
  exit 1
} finally {
  Stop-Transcript | Out-Null
}
