param([switch]$Full)
$ErrorActionPreference = 'Stop'
$root = (git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Run inside your Git repository.' }
Set-Location $root
Write-Host "Repository: $root" -ForegroundColor Cyan
$branch = (git branch --show-current).Trim()
Write-Host "Branch: $branch"
if ($branch -ne 'phase5-production-deployment') { throw 'Expected phase5-production-deployment branch.' }
$requirements = @('backend/app/main.py','backend/alembic.ini','frontend/package.json','compose.phase5-app.yml','backend/Dockerfile.phase5','frontend/Dockerfile.phase5')
foreach ($file in $requirements) { if (-not (Test-Path $file)) { throw "Missing file: $file" } }
$private = @('.env.phase5.local','backend/.env','frontend/.env.local')
foreach ($file in $private) { if (Test-Path $file) { Write-Host "Present locally (do not commit): $file" -ForegroundColor Yellow } }
$tracked = @(git ls-files | Where-Object { $_ -match '(^|/)\.env($|\.)' -and $_ -notmatch '\.example$' })
if ($tracked.Count) { $tracked | ForEach-Object { Write-Host "TRACKED SECRET CANDIDATE: $_" -ForegroundColor Red }; throw 'Fix tracked environment files first.' }
$staged = @(git diff --cached --name-only)
$bad = @($staged | Where-Object { $_ -match '(^|/)\.env($|\.)' -and $_ -notmatch '\.example$' })
if ($bad.Count) { throw 'Private environment file staged.' }
Write-Host 'Preflight files and tracking: PASS' -ForegroundColor Green
if ($Full) {
  Push-Location backend
  try { & '.\.venv\Scripts\python.exe' -m pytest -q; if ($LASTEXITCODE -ne 0) { throw 'Pytest failed' } }
  finally { Pop-Location }
  Push-Location frontend
  try {
    npm run typecheck; if ($LASTEXITCODE -ne 0) { throw 'Typecheck failed' }
    npm run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
  }
  finally { Pop-Location }
}
