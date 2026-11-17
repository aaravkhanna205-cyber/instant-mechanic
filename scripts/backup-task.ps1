# Started by the Windows task "InstantMechanicHire-Backup" every day. Log: $HOME\imhire-logs\backup.log
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$logDir = Join-Path $HOME 'imhire-logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path (Join-Path $logDir 'backup.log') -Append | Out-Null
Write-Host "$(Get-Date -Format s) daily backup"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'selfhost.ps1') -Backup
$code = $LASTEXITCODE
Write-Host "$(Get-Date -Format s) finished with code $code"
Stop-Transcript | Out-Null
exit $code
