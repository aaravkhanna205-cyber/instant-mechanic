# Make the site start by itself and back itself up every day (Windows Task Scheduler).
#   Install:  powershell -ExecutionPolicy Bypass -File .\scripts\windows-tasks.ps1 -Install
#   Install with another backup time:  ... -Install -BackupTime 23:00
#   Check:    powershell -ExecutionPolicy Bypass -File .\scripts\windows-tasks.ps1 -Status
#   Remove:   powershell -ExecutionPolicy Bypass -File .\scripts\windows-tasks.ps1 -Remove
# The tasks run as you, only while you are signed in (Docker Desktop needs that anyway). No password is stored.
param([switch]$Install, [switch]$Remove, [switch]$Status, [string]$BackupTime = '13:30')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$names = @('InstantMechanicHire-Start', 'InstantMechanicHire-Backup')

if ($Remove) {
  foreach ($name in $names) { Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue }
  Write-Host 'Automatic start and daily backup removed.' -ForegroundColor Yellow
  exit 0
}

if ($Install) {
  $user = "$env:USERDOMAIN\$env:USERNAME"
  $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew

  $startAction = New-ScheduledTaskAction -Execute 'powershell.exe' -WorkingDirectory $root `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$root\scripts\start-on-logon.ps1`""
  $startTrigger = New-ScheduledTaskTrigger -AtLogOn -User $user
  $startTrigger.Delay = 'PT2M'   # give Docker Desktop a head start
  Register-ScheduledTask -TaskName $names[0] -Action $startAction -Trigger $startTrigger -Principal $principal `
    -Settings $settings -Description 'Starts Instant Mechanic Hire after you sign in.' -Force | Out-Null

  $backupAction = New-ScheduledTaskAction -Execute 'powershell.exe' -WorkingDirectory $root `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$root\scripts\backup-task.ps1`""
  $backupTrigger = New-ScheduledTaskTrigger -Daily -At $BackupTime
  Register-ScheduledTask -TaskName $names[1] -Action $backupAction -Trigger $backupTrigger -Principal $principal `
    -Settings $settings -Description 'Daily backup of the Instant Mechanic Hire database and resumes (keeps 14).' -Force | Out-Null

  Write-Host 'Installed:' -ForegroundColor Green
  Write-Host "  - The site starts by itself 2 minutes after you sign in."
  Write-Host "  - A backup runs every day at $BackupTime (or as soon as the PC is on after that). The newest 14 are kept in $HOME\imhire-backups"
  Write-Host '  - Logs: ' -NoNewline; Write-Host "$HOME\imhire-logs"
  Write-Host 'Also do this once: Docker Desktop > Settings > General > tick "Start Docker Desktop when you sign in".' -ForegroundColor Yellow
  exit 0
}

# Status (default)
foreach ($name in $names) {
  $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
  if (-not $task) { Write-Host "MISSING  $name (run with -Install)" -ForegroundColor Yellow; continue }
  $info = Get-ScheduledTaskInfo -TaskName $name
  $result = if ($info.LastTaskResult -eq 0) { 'OK' } elseif ($info.LastRunTime.Year -lt 2000) { 'not run yet' } else { "code $($info.LastTaskResult)" }
  Write-Host ("{0,-28} last run: {1}  result: {2}  next: {3}" -f $name, $info.LastRunTime, $result, $info.NextRunTime)
}
$latest = Get-ChildItem (Join-Path $HOME 'imhire-backups') -Filter 'db-*.dump' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($latest) { Write-Host "Newest backup: $($latest.Name) ($($latest.LastWriteTime))" } else { Write-Host 'No backup yet.' -ForegroundColor Yellow }
