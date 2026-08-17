param(
    [string]$EnvironmentFile = "deploy/production.env",
    [string]$ComposeFile = "compose.production.yaml"
)

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "preflight.ps1") -EnvironmentFile $EnvironmentFile -ComposeFile $ComposeFile
if ($LASTEXITCODE -ne 0) { throw "preflight failed" }

docker compose --env-file $EnvironmentFile -f $ComposeFile build
if ($LASTEXITCODE -ne 0) { throw "image build failed" }
docker compose --env-file $EnvironmentFile -f $ComposeFile run --rm migrate
if ($LASTEXITCODE -ne 0) { throw "database migration failed" }
docker compose --env-file $EnvironmentFile -f $ComposeFile up -d --force-recreate sector-bootstrap public-data-bootstrap api sector-scheduler public-data-scheduler gateway prometheus
if ($LASTEXITCODE -ne 0) { throw "service rollout failed" }
