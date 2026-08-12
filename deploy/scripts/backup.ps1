param(
    [Parameter(Mandatory=$true)][string]$DatabaseUrl,
    [string]$BackupDirectory = "deploy/backups"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$target = [System.IO.Path]::GetFullPath((Join-Path $root $BackupDirectory))
if (-not $target.StartsWith($root)) { throw "Backup directory must stay inside the repository" }
New-Item -ItemType Directory -Path $target -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = Join-Path $target "database-$stamp.dump"
pg_dump --dbname=$DatabaseUrl --format=custom --file=$backup
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $backup).Hash
@{created_at=(Get-Date).ToUniversalTime().ToString("o"); backup=(Split-Path $backup -Leaf); sha256=$hash} | ConvertTo-Json | Set-Content -Encoding UTF8 "$backup.json"
Write-Output $backup
