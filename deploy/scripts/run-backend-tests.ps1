param(
    [string]$ComposeFile = "compose.test.yaml",
    [string]$TestDatabaseUrl = "postgresql+psycopg://vibe_test:vibe_test_local_only@127.0.0.1:55432/vibe_research_test",
    [switch]$RemoveVolume
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$resolvedCompose = (Resolve-Path (Join-Path $repositoryRoot $ComposeFile)).Path
$backend = (Resolve-Path (Join-Path $repositoryRoot "backend")).Path
$python = (Resolve-Path (Join-Path $backend ".venv\Scripts\python.exe")).Path

if ($TestDatabaseUrl -notmatch '/[^/?#]*_test(?:\?|$)') {
    throw "Test database name must end with _test"
}

Push-Location $repositoryRoot
try {
    docker compose -f $resolvedCompose up -d --wait postgres-test
    if ($LASTEXITCODE -ne 0) { throw "Disposable PostgreSQL did not become healthy" }
    $env:VR_TEST_DATABASE_URL = $TestDatabaseUrl
    $env:VR_DATABASE_URL = $TestDatabaseUrl
    Push-Location $backend
    try {
        & $python -m alembic -c alembic.ini upgrade head
        if ($LASTEXITCODE -ne 0) { throw "Alembic migration failed" }
        & $python -m pytest -m "not live" -q
        if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }
    } finally {
        Pop-Location
    }
} finally {
    if ($RemoveVolume) {
        docker compose -f $resolvedCompose down --volumes
    }
    Pop-Location
}
