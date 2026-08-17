param(
    [string]$EnvironmentFile = "deploy/production.env",
    [string]$ComposeFile = "compose.production.yaml"
)

$ErrorActionPreference = "Stop"

function Read-EnvironmentFile([string]$Path) {
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $parts = $trimmed.Split("=", 2)
        if ($parts.Count -ne 2) { throw "Invalid environment entry: $trimmed" }
        $values[$parts[0].Trim()] = $parts[1].Trim()
    }
    return $values
}

$environmentPath = (Resolve-Path -LiteralPath $EnvironmentFile).Path
$composePath = (Resolve-Path -LiteralPath $ComposeFile).Path
$values = Read-EnvironmentFile $environmentPath
$required = @("VR_DEPLOYMENT_MODE", "VR_DATABASE_URL", "TEAJOIN_API_KEY", "POSTGRES_PASSWORD", "REDIS_PASSWORD")
foreach ($name in $required) {
    if (-not $values.ContainsKey($name) -or -not $values[$name] -or $values[$name] -match "CHANGE_ME") {
        throw "Production environment variable is missing or still a placeholder: $name"
    }
}
if ($values["VR_DEPLOYMENT_MODE"] -ne "public") { throw "VR_DEPLOYMENT_MODE must be public" }
if ($values.ContainsKey("VR_ALLOW_ORIGINS") -and $values["VR_ALLOW_ORIGINS"] -notmatch "^https://") {
    throw "VR_ALLOW_ORIGINS must contain only HTTPS origins in production"
}
docker compose --env-file $environmentPath -f $composePath config --quiet
if ($LASTEXITCODE -ne 0) { throw "docker compose configuration validation failed" }
@{ status = "passed"; environment_file = $environmentPath; compose_file = $composePath } | ConvertTo-Json -Compress
