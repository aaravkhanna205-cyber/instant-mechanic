# Opens two console windows: the scheduler (drafts only) and the worker (outbox mode unless you configured SMTP).
# Run from anywhere inside the repository:  .\scripts\phase6\Start-Phase6-Workers.ps1
$ErrorActionPreference='Stop'
$root=(& git -C $PSScriptRoot rev-parse --show-toplevel 2>$null | Select-Object -First 1)
if([string]::IsNullOrWhiteSpace($root)){throw 'Could not find the Git repository root.'}
$backend=Join-Path $root 'backend'
$python=Join-Path (Join-Path (Join-Path $backend '.venv') 'Scripts') 'python.exe'
if(-not(Test-Path $python)){throw "Python environment not found: $python"}
if(-not(Test-Path (Join-Path $backend '.env'))){throw 'backend\.env is missing.'}
foreach($module in @('app.phase6_agents.scheduler','app.phase6_agents.worker')){
  $line='Set-Location "'+$backend+'"; & "'+$python+'" -m '+$module
  Start-Process powershell.exe -ArgumentList @('-NoProfile','-NoExit','-Command',$line) | Out-Null
}
Write-Host 'Two consoles opened. Keep them running. Outbox mode does NOT send real email.' -ForegroundColor Green
