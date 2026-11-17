# Prove the newest backup can really be restored, WITHOUT touching the live database.
#   powershell -ExecutionPolicy Bypass -File .\scripts\restore-test.ps1
# It restores into a temporary database container, counts the rows, then deletes the container.
param([string]$File = '')
$ErrorActionPreference = 'Stop'
$dir = Join-Path $HOME 'imhire-backups'
if (-not $File) {
  $latest = Get-ChildItem $dir -Filter 'db-*.dump' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $latest) { throw "No backup found in $dir. Run .\scripts\selfhost.ps1 -Backup first." }
  $File = $latest.FullName
}
$name = 'imhire-restore-test'
$secret = [guid]::NewGuid().ToString('N')
Write-Host "Testing $File" -ForegroundColor Cyan
& docker rm -f $name 2>$null | Out-Null
& docker run -d --name $name -e POSTGRES_PASSWORD=$secret -e POSTGRES_DB=restoretest -v "${dir}:/backup:ro" pgvector/pgvector:pg17 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not start a temporary database (is Docker running?).' }
try {
  for ($i = 0; $i -lt 30; $i++) {
    & docker exec $name pg_isready -U postgres -d restoretest 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
  }
  Start-Sleep -Seconds 3
  $leaf = Split-Path $File -Leaf
  & docker exec $name pg_restore -U postgres -d restoretest --no-owner --no-privileges "/backup/$leaf"
  if ($LASTEXITCODE -ne 0) { Write-Host 'pg_restore reported warnings (often harmless); checking the data...' -ForegroundColor Yellow }
  $sql = "SELECT 'version ' || version_num FROM alembic_version UNION ALL " +
         "SELECT 'users ' || count(*) FROM users UNION ALL SELECT 'jobs ' || count(*) FROM jobs UNION ALL " +
         "SELECT 'applications ' || count(*) FROM applications UNION ALL SELECT 'interviews ' || count(*) FROM interviews"
  $out = & docker exec $name psql -U postgres -d restoretest -t -A -c $sql
  if ($LASTEXITCODE -ne 0 -or -not ($out -match 'version ')) { throw 'The restored copy is not usable.' }
  $out | ForEach-Object { Write-Host "  $_" }
  $resumes = Get-ChildItem $dir -Filter 'resumes-*.tar.gz' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($resumes) {
    $count = (& docker run --rm -v "${dir}:/backup:ro" alpine tar tzf "/backup/$($resumes.Name)" | Measure-Object).Count
    Write-Host "  resume archive $($resumes.Name): $count entries"
  }
  Write-Host 'RESTORE TEST PASSED - this backup can be restored.' -ForegroundColor Green
} finally {
  & docker rm -f $name | Out-Null
}
