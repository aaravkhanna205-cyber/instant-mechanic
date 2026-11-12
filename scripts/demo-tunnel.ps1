# Free public demo link for the app running in Docker on this PC.
#   Start:  powershell -ExecutionPolicy Bypass -File .\scripts\demo-tunnel.ps1
#   Stop:   powershell -ExecutionPolicy Bypass -File .\scripts\demo-tunnel.ps1 -Stop
#   Limit who can open the link (they confirm their email with a code):
#           ... -File .\scripts\demo-tunnel.ps1 -AllowedMail "a@example.com,b@example.com"
# Demo only: the link changes on every start and dies when the PC or Docker stops.
param([switch]$Stop, [string]$AllowedMail = '')
$ErrorActionPreference = 'Stop'

$root = (git rev-parse --show-toplevel).Trim()
Set-Location $root
foreach ($file in @('.env.phase5.local', 'compose.phase5-app.yml', 'compose.tunnel.yml', 'deploy/Caddyfile.tunnel')) {
  if (-not (Test-Path $file)) { throw "Missing $file. Finish the Phase 5 Docker rehearsal setup first." }
}
$files = '--env-file .env.phase5.local -f compose.phase5-app.yml -f compose.tunnel.yml'
$dc = @('compose', '--profile', 'worker', '--env-file', '.env.phase5.local', '-f', 'compose.phase5-app.yml', '-f', 'compose.tunnel.yml')

if ($Stop) {
  & docker @dc stop
  Write-Host 'Demo stopped. The public link no longer works.' -ForegroundColor Yellow
  exit 0
}

cmd /c "docker info >nul 2>&1"
if ($LASTEXITCODE -ne 0) { throw 'Docker is not running. Start Docker Desktop, wait until it is ready, then run this again.' }

# The PC worker and the container worker share one queue; only one may run.
if ($env:OS -eq 'Windows_NT') {
  Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like '*phase4_ai.worker*' -and $_.Name -like 'python*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

$env:TUNNEL_URL = ''
$env:TUNNEL_ARGS = ''
if ($AllowedMail.Trim()) { $env:TUNNEL_ARGS = '--allowed-mail ' + $AllowedMail.Trim().Replace(' ', '') }

Write-Host 'Opening the tunnel...' -ForegroundColor Cyan
& docker @dc up -d --force-recreate proxy tunnel
if ($LASTEXITCODE -ne 0) { throw 'Could not start the tunnel containers.' }

$url = $null
for ($i = 0; $i -lt 45 -and -not $url; $i++) {
  Start-Sleep -Seconds 2
  $logs = (cmd /c "docker compose $files logs --no-color tunnel 2>&1" | Out-String)
  $found = [regex]::Matches($logs, 'https://[a-z0-9-]+\.trycloudflare\.com')
  if ($found.Count -gt 0) { $url = $found[$found.Count - 1].Value }
}
if (-not $url) { throw 'No public address appeared. Check your internet connection, then run this again.' }

Write-Host "Public address: $url" -ForegroundColor Cyan
Write-Host 'Building and starting the app (the first time takes several minutes)...' -ForegroundColor Cyan
$env:TUNNEL_URL = $url
& docker @dc up -d --build api worker web
if ($LASTEXITCODE -ne 0) { throw 'Could not start the app containers.' }

$ready = $false
for ($i = 0; $i -lt 40 -and -not $ready; $i++) {
  Start-Sleep -Seconds 3
  try {
    $check = Invoke-RestMethod 'http://127.0.0.1:18000/api/ready' -TimeoutSec 5
    if ($check.status -eq 'ready') { $ready = $true }
  } catch { }
}
if (-not $ready) { throw 'The API did not become ready. Make sure your database and Redis are running, then run this again.' }

Write-Host ''
Write-Host 'DEMO IS LIVE' -ForegroundColor Green
Write-Host "  $url" -ForegroundColor Green
Write-Host 'Share this link. It works only while this PC and Docker stay on.' -ForegroundColor Yellow
Write-Host 'Stop it with: powershell -ExecutionPolicy Bypass -File .\scripts\demo-tunnel.ps1 -Stop' -ForegroundColor Yellow
