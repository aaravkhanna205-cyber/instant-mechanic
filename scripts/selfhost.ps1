# Self-host the app on this PC behind a fixed public HTTPS address.
#   Start:   powershell -ExecutionPolicy Bypass -File .\scripts\selfhost.ps1 -PublicUrl https://NAME.TAILNET.ts.net
#   Restart: powershell -ExecutionPolicy Bypass -File .\scripts\selfhost.ps1            (remembers the address)
#   Verify:  powershell -ExecutionPolicy Bypass -File .\scripts\selfhost.ps1 -Verify
#   Backup:  powershell -ExecutionPolicy Bypass -File .\scripts\selfhost.ps1 -Backup
#   Stop:    powershell -ExecutionPolicy Bypass -File .\scripts\selfhost.ps1 -Stop
param([string]$PublicUrl = '', [switch]$Verify, [switch]$Backup, [switch]$Stop)
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

$root = (git rev-parse --show-toplevel).Trim()
Set-Location $root
foreach ($file in @('.env.phase5.local', 'compose.phase5-app.yml', 'compose.selfhost.yml', 'deploy/Caddyfile.tunnel')) {
  if (-not (Test-Path $file)) { throw "Missing $file. Finish the Phase 5 Docker rehearsal setup first." }
}
$dc = @('compose', '--profile', 'worker', '--env-file', '.env.phase5.local', '-f', 'compose.phase5-app.yml', '-f', 'compose.selfhost.yml')
$urlFile = Join-Path $root '.env.selfhost.local'

function Get-SavedUrl {
  if (Test-Path $urlFile) {
    foreach ($line in Get-Content $urlFile) { if ($line -match '^PUBLIC_URL=(.+)$') { return $Matches[1].Trim() } }
  }
  return ''
}

function Get-Status([string]$Url, [string]$Method = 'GET', [hashtable]$Headers = @{}, [string]$Body = '') {
  try {
    $params = @{ Uri = $Url; Method = $Method; Headers = $Headers; UseBasicParsing = $true; TimeoutSec = 25 }
    if ($Body) { $params['Body'] = $Body; $params['ContentType'] = 'application/json' }
    $response = Invoke-WebRequest @params
    return [int]$response.StatusCode
  } catch {
    if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
    return 0
  }
}

if ($Stop) {
  & docker @dc stop
  Write-Host 'Self-hosted app stopped. The public address will not answer until you start it again.' -ForegroundColor Yellow
  exit 0
}

if ($Backup) {
  $dir = Join-Path $HOME 'imhire-backups'
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss')
  $dbUrl = ''
  foreach ($line in Get-Content '.env.phase5.local') { if ($line -match '^DATABASE_URL=(.+)$') { $dbUrl = $Matches[1].Trim() } }
  if (-not $dbUrl) { throw 'DATABASE_URL not found in .env.phase5.local' }
  $dbUrl = $dbUrl -replace '^postgresql\+[a-z0-9]+://', 'postgresql://'
  & docker run --rm -v "${dir}:/backup" pgvector/pgvector:pg17 pg_dump "--dbname=$dbUrl" -Fc -f "/backup/db-$stamp.dump"
  if ($LASTEXITCODE -ne 0) { throw 'Database backup failed. Is the database running?' }
  & docker run --rm -v "${dir}:/backup" pgvector/pgvector:pg17 pg_restore --list "/backup/db-$stamp.dump" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'The backup file could not be read back.' }
  & docker run --rm -v 'imhire_phase5_app_resume_private_data:/data:ro' -v "${dir}:/backup" alpine tar czf "/backup/resumes-$stamp.tar.gz" -C /data .
  if ($LASTEXITCODE -ne 0) { throw 'Resume backup failed.' }
  Get-ChildItem $dir -File | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } | Remove-Item -Force
  Write-Host "Backup written and read back: $dir\db-$stamp.dump and resumes-$stamp.tar.gz" -ForegroundColor Green
  Write-Host 'Copy this folder to another disk or drive regularly.' -ForegroundColor Yellow
  exit 0
}

if ($Verify) {
  $base = Get-SavedUrl
  if (-not $base) { throw 'No saved address. Start first with -PublicUrl.' }
  $script:failures = 0
  function Check([string]$Name, $Got, $Expected) {
    if ("$Got" -eq "$Expected") { Write-Host "PASS  $Name" -ForegroundColor Green }
    else { Write-Host "FAIL  $Name (expected $Expected, got $Got)" -ForegroundColor Red; $script:failures++ }
  }
  Write-Host "== Checking $base" -ForegroundColor Cyan
  Check 'Address uses HTTPS' $base.StartsWith('https://') $true
  Check 'API health over the public address' (Get-Status "$base/api/health") 200
  Check 'Database and Redis ready' (Get-Status "$base/api/ready") 200
  Check 'Login page loads' (Get-Status "$base/auth-live") 200
  Check 'Anonymous /api/auth/me is refused' (Get-Status "$base/api/auth/me") 401
  Check 'Anonymous resume list is refused' (Get-Status "$base/api/phase4/resumes/mine") 401
  $foreign = Get-Status "$base/api/auth/login" 'POST' @{ Origin = 'https://evil.example' } '{"email":"nobody@example.com","password":"x"}'
  Check 'Login from a foreign website is refused' $foreign 403
  foreach ($path in @('/docs', '/redoc', '/openapi.json')) {
    $status = Get-Status "$base$path"
    Check "API documentation $path is not public" ($status -ne 200) $true
  }
  try {
    $headers = (Invoke-WebRequest "$base/api/health" -UseBasicParsing -TimeoutSec 25).Headers
    Check 'nosniff header present' ("$($headers['X-Content-Type-Options'])" -eq 'nosniff') $true
  } catch { Check 'nosniff header present' $false $true }
  $scan = (& docker @dc exec -T api python -m scripts.verify_scanner | Out-String)
  Check 'Malware scanner accepts clean files and blocks the test virus' ($scan -match 'SCANNER OK') $true
  $schema = (& docker @dc exec -T api python -m scripts.verify_phase4 | Out-String)
  Check 'Database at latest version with pgvector' ($schema -match 'PHASE 4 SCHEMA READY') $true
  $mode = (& docker @dc exec -T api python -c "from app.security.sessions import cookie_options as c; o=c(); print('COOKIE', o['secure'], o['httponly'])" | Out-String)
  Check 'Login cookie is Secure and HttpOnly' ($mode -match 'COOKIE True True') $true
  $recent = Get-ChildItem (Join-Path $HOME 'imhire-backups') -Filter 'db-*.dump' -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-2) }
  if ($recent) { Write-Host 'PASS  Backup from the last 2 days exists' -ForegroundColor Green }
  else { Write-Host 'WARN  No recent backup. Run this script with -Backup' -ForegroundColor Yellow }
  Write-Host ''
  if ($script:failures -eq 0) {
    Write-Host 'ALL AUTOMATED CHECKS PASSED' -ForegroundColor Green
    Write-Host 'Still to check by hand in a browser: sign in, upload a resume, recruiter evidence, sign out.'
    exit 0
  }
  Write-Host "$($script:failures) CHECK(S) FAILED" -ForegroundColor Red
  exit 1
}

# ---- Start ----
if ($PublicUrl) {
  $PublicUrl = $PublicUrl.Trim().TrimEnd('/')
  if ($PublicUrl -notmatch '^https://[A-Za-z0-9.-]+$') { throw 'PublicUrl must look like https://name.tailnet.ts.net (https, no path).' }
  Set-Content -Path $urlFile -Value "PUBLIC_URL=$PublicUrl" -Encoding ascii
}
$url = Get-SavedUrl
if (-not $url) { throw 'First start needs the address: add  -PublicUrl https://NAME.TAILNET.ts.net' }

cmd /c "docker info >nul 2>&1"
if ($LASTEXITCODE -ne 0) { throw 'Docker is not running. Start Docker Desktop, wait until it is ready, then run this again.' }

# The PC worker and the container worker share one queue; only one may run.
if ($env:OS -eq 'Windows_NT') {
  Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like '*phase4_ai.worker*' -and $_.Name -like 'python*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

Write-Host "Starting the app for $url (the first time takes several minutes)..." -ForegroundColor Cyan
$env:PUBLIC_URL = $url
& docker @dc up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Could not start the containers.' }

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
Write-Host 'APP IS RUNNING' -ForegroundColor Green
Write-Host "  Public address: $url" -ForegroundColor Green
Write-Host '  It answers only while this PC, Docker Desktop and the tunnel are on.' -ForegroundColor Yellow
Write-Host '  Wait about 5 minutes for the malware scanner, then run this script with -Verify' -ForegroundColor Yellow
