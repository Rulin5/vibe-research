param(
    [Parameter(Mandatory=$true)][string]$DnsName,
    [string]$OutputDirectory = "deploy/certs"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$target = [System.IO.Path]::GetFullPath((Join-Path $root $OutputDirectory))
if (-not $target.StartsWith($root)) { throw "Certificate output must stay inside the repository" }
New-Item -ItemType Directory -Path $target -Force | Out-Null

$certificate = New-SelfSignedCertificate -DnsName $DnsName -CertStoreLocation "Cert:\CurrentUser\My" -NotAfter (Get-Date).AddDays(30) -FriendlyName "Vibe Research staging only"
$password = ConvertTo-SecureString ([Guid]::NewGuid().ToString()) -AsPlainText -Force
Export-PfxCertificate -Cert $certificate -FilePath (Join-Path $target "staging.pfx") -Password $password | Out-Null
Write-Output "Created staging-only certificate. This is not public-trust TLS evidence."
