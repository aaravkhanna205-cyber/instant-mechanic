# Without -Push: runs every automated check and changes nothing.
# With -Push: also commits the Phase 6 files and pushes the feature branch after you confirm. Never touches main/master.
param([switch]$Push)
$ErrorActionPreference='Stop'
$root=(& git -C $PSScriptRoot rev-parse --show-toplevel 2>$null | Select-Object -First 1)
if([string]::IsNullOrWhiteSpace($root)){throw 'Could not find the Git repository root.'}
Set-Location $root
$branch=(& git branch --show-current).Trim()
if($branch -ne 'phase6-agentic-automation'){throw "You are on '$branch'. Switch to phase6-agentic-automation first."}
$python=Join-Path (Join-Path (Join-Path (Join-Path $root 'backend') '.venv') 'Scripts') 'python.exe'
if(-not(Test-Path $python)){throw 'Backend Python environment missing.'}
Push-Location (Join-Path $root 'backend')
try{
  & $python -m pytest -q
  if($LASTEXITCODE -ne 0){throw 'Backend tests failed.'}
  & $python -m scripts.verify_phase6
  if($LASTEXITCODE -ne 0){throw 'Phase 6 database verification failed.'}
}finally{Pop-Location}
Push-Location (Join-Path $root 'frontend')
try{
  npm run typecheck
  if($LASTEXITCODE -ne 0){throw 'TypeScript check failed.'}
  npx next build --webpack
  if($LASTEXITCODE -ne 0){throw 'Next.js build failed.'}
}finally{Pop-Location}
Write-Host 'Automated Phase 6 checks passed. The browser walk-through is a separate, manual check.' -ForegroundColor Green
if(-not $Push){Write-Host 'Check-only run: nothing staged, committed or pushed.';exit 0}
$files=@('backend/app/phase6_agents','backend/alembic/versions/0006_phase6_agents.py','backend/scripts/phase6_register.py','backend/scripts/verify_phase6.py','backend/scripts/phase6_demo.py','backend/tests/test_phase6_full.py','backend/tests/test_phase6_http.py','backend/requirements-phase6.txt','backend/.env.phase6.example','backend/app/main.py','frontend/app/phase6','docs/PHASE6-COMPLETE-GUIDE.md','scripts/phase6','.github/workflows/phase6-tests.yml')
foreach($f in $files){if(-not(Test-Path $f)){throw "Expected file missing: $f"}}
git add -- $files
if($LASTEXITCODE -ne 0){throw 'Git staging failed.'}
$staged=@(git diff --cached --name-only)
foreach($f in $staged){
  if(($f -match '(^|/)\.env($|\.)' -and $f -notmatch '\.example$') -or $f -match '(\.pem|\.p12|\.pfx|\.key)$' -or $f -match '(/\.venv/|/node_modules/)'){
    throw "Sensitive or generated file staged: $f"
  }
}
Write-Host 'STAGED FILES:' -ForegroundColor Yellow
$staged | ForEach-Object {Write-Host "  $_"}
$answer=Read-Host 'If the browser walk-through passed and no secrets are listed above, type PUSH-PHASE6'
if($answer -cne 'PUSH-PHASE6'){throw 'Push cancelled. The files stay staged for you to review.'}
git commit -m 'feat: Phase 6 human-approved recruitment automation'
if($LASTEXITCODE -ne 0){throw 'Commit failed.'}
git push -u origin HEAD
if($LASTEXITCODE -ne 0){throw 'Push failed. The commit is saved locally.'}
git status
Write-Host 'Phase 6 pushed to the feature branch. main/master was not changed.' -ForegroundColor Green
