[CmdletBinding()]
param(
    [switch]$ResetConfig
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $root "deploy/demo.env"
$composePath = Join-Path $root "compose.demo.yaml"

function New-RandomBase64([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
    return [Convert]::ToBase64String($buffer).Replace("+", "-").Replace("/", "_")
}

function New-RandomHex([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
    return -join ($buffer | ForEach-Object { $_.ToString("x2") })
}

function Read-Secret([string]$Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "未找到 Docker。请先安装并启动 Docker Desktop。"
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop 尚未启动。" }

if ($ResetConfig -or -not (Test-Path -LiteralPath $envPath)) {
    Write-Host "首次启动：密钥只写入本机 deploy/demo.env，不会上传 GitHub。" -ForegroundColor Cyan
    $teaJoinKey = Read-Secret "TeaJoin API Key"
    $stepFunKey = Read-Secret "StepFun API Key（可留空，之后在页面配置）"
    $dbPassword = New-RandomHex 24
    $redisPassword = New-RandomHex 24
    $sessionSecret = New-RandomBase64 48
    $credentialKey = New-RandomBase64 32
    $lines = @(
        "POSTGRES_DB=vibe_research",
        "POSTGRES_USER=vibe_user",
        "POSTGRES_PASSWORD=$dbPassword",
        "REDIS_PASSWORD=$redisPassword",
        "VR_DATABASE_URL=postgresql+psycopg://vibe_user:$dbPassword@postgres:5432/vibe_research",
        "VR_REDIS_URL=redis://:$redisPassword@redis:6379/0",
        "TEAJOIN_API_KEY=$teaJoinKey",
        "VR_SESSION_SECRET=$sessionSecret",
        "VR_CREDENTIAL_ENCRYPTION_KEY=$credentialKey",
        "VR_CREDENTIAL_ENCRYPTION_KEY_PREVIOUS=",
        "VR_ALLOW_ORIGINS=http://127.0.0.1:5900",
        "VR_DEPLOYMENT_MODE=local",
        "VR_COOKIE_SECURE=false",
        "VR_AI_ALLOWED_HOSTS=api.stepfun.com",
        "VR_REPORTS_DIR=/data/reports",
        "VR_REPORT_SCAN_COMMAND=clamdscan --config-file=/etc/clamav/clamd.remote.conf --stream --no-summary {path}",
        "VR_AI_STEPFUN_BASE_URL=https://api.stepfun.com/step_plan/v1",
        "VR_AI_STEPFUN_MODEL=step-3.7-flash",
        "VR_AI_STEPFUN_API_KEY=$stepFunKey"
    )
    [IO.File]::WriteAllLines($envPath, $lines, (New-Object Text.UTF8Encoding($false)))
}

Push-Location $root
try {
    docker compose -f $composePath up -d --build --wait
    if ($LASTEXITCODE -ne 0) { throw "启动失败，请运行 docker compose -f compose.demo.yaml logs 查看原因。" }
    Write-Host "启动完成：http://127.0.0.1:5900" -ForegroundColor Green
    Start-Process "http://127.0.0.1:5900"
} finally {
    Pop-Location
}
