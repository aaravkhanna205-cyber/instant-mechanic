$ErrorActionPreference='Stop'
$root=(git rev-parse --show-toplevel).Trim(); Set-Location $root
$branch=(git branch --show-current).Trim(); if ($branch -ne 'phase5-production-deployment') { throw 'Wrong branch' }
Write-Host 'Current changes:' -ForegroundColor Cyan
git status --short
Write-Host 'Files staged for commit:' -ForegroundColor Cyan
git diff --cached --name-only
$unsafe=@(git diff --cached --name-only | Where-Object { ($_ -match '(^|/)\.env($|\.)' -and $_ -notmatch '\.example$') -or $_ -match '\.(pem|key|p12|pfx)$' })
if($unsafe.Count) { $unsafe; throw 'Sensitive files staged. Do not commit.' }
Write-Host 'Filename safety check passed. Manually review contents for secrets before commit.' -ForegroundColor Green
