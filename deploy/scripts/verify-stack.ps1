param(
    [Parameter(Mandatory=$true)][string]$BaseUrl,
    [Parameter(Mandatory=$true)][string]$EicarFile,
    [string]$EvidencePath = "deploy/evidence/stack-verification.json"
)

$ErrorActionPreference = "Stop"
if (-not $BaseUrl.StartsWith("https://")) { throw "BaseUrl must use https://" }
$eicar = (Resolve-Path -LiteralPath $EicarFile).Path
$health = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/api/health" -TimeoutSec 10
$ready = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/api/ready" -TimeoutSec 10
if ($health.StatusCode -ne 200 -or $ready.StatusCode -ne 200) { throw "Health or readiness failed" }
if (-not $health.Headers["Strict-Transport-Security"]) { throw "Strict-Transport-Security header is missing" }
# Upload requires an operator-created authenticated test session. Evidence must be supplied after the EICAR upload returns 400.
$eicarHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $eicar).Hash
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$evidence = [System.IO.Path]::GetFullPath((Join-Path $root $EvidencePath))
if (-not $evidence.StartsWith($root)) { throw "Evidence path must stay inside the repository" }
New-Item -ItemType Directory -Path (Split-Path $evidence) -Force | Out-Null
@{status="partial"; https_health=200; https_ready=200; hsts=$true; eicar_sha256=$eicarHash; eicar_upload_rejected=$false; note="Set eicar_upload_rejected only after authenticated HTTP 400 evidence is attached."} | ConvertTo-Json | Set-Content -Encoding UTF8 $evidence
throw "EICAR authenticated upload evidence is still required"
