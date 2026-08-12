param(
    [Parameter(Mandatory=$true)][string]$BackupPath,
    [Parameter(Mandatory=$true)][string]$RestoreDatabaseUrl,
    [string]$EvidencePath = "deploy/evidence/restore-drill.json"
)

$ErrorActionPreference = "Stop"
$backup = (Resolve-Path -LiteralPath $BackupPath).Path
if ($RestoreDatabaseUrl -notmatch '/[^/?#]*_restore_test(?:\?|$)') { throw "Restore database name must end with _restore_test" }
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$evidence = [System.IO.Path]::GetFullPath((Join-Path $root $EvidencePath))
if (-not $evidence.StartsWith($root)) { throw "Evidence path must stay inside the repository" }
New-Item -ItemType Directory -Path (Split-Path $evidence) -Force | Out-Null
pg_restore --clean --if-exists --no-owner --dbname=$RestoreDatabaseUrl $backup
if ($LASTEXITCODE -ne 0) { throw "pg_restore failed" }
$tables = psql $RestoreDatabaseUrl --tuples-only --no-align --command="select count(*) from information_schema.tables where table_schema='public';"
if ($LASTEXITCODE -ne 0 -or [int]$tables -lt 1) { throw "Restored database verification failed" }
@{status="passed"; completed_at=(Get-Date).ToUniversalTime().ToString("o"); backup_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $backup).Hash; public_tables=[int]$tables} | ConvertTo-Json | Set-Content -Encoding UTF8 $evidence
