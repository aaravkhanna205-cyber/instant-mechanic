param([string]$Api='http://127.0.0.1:8000',[string]$Web='http://127.0.0.1:3000')
$ErrorActionPreference = 'Stop'
try {
  $health = Invoke-RestMethod "$Api/api/health" -TimeoutSec 15
  Write-Host "Health endpoint OK: $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
  $ready = Invoke-RestMethod "$Api/api/ready" -TimeoutSec 15
  if ($ready.status -ne 'ready' -or -not $ready.checks.postgres -or -not $ready.checks.redis) { throw 'Readiness checks failed' }
  Write-Host 'Postgres and Redis readiness: PASS' -ForegroundColor Green
  $page = Invoke-WebRequest "$Web/phase4" -UseBasicParsing -TimeoutSec 20
  if ($page.StatusCode -ne 200) { throw "Frontend returned HTTP $($page.StatusCode)" }
  Write-Host 'Frontend HTTP check: PASS' -ForegroundColor Green
  Write-Host 'NOTE: HTTP checks do not prove authentication, resume pipeline or browser correctness.' -ForegroundColor Yellow
} catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
