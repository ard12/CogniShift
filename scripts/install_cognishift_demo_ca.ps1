# Install CogniShift Local Demo CA into CurrentUser Root store
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$CaCertPath = Join-Path $ProjectRoot "data\certs\cognishift_demo_ca.crt"

if (-not (Test-Path $CaCertPath)) {
    Write-Error "Certificate not found at $CaCertPath. Run scripts\generate_local_tls.py first."
    exit 1
}

Write-Host "Installing CogniShift Demo CA into CurrentUser\Root..." -ForegroundColor Cyan
try {
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($CaCertPath)
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
    $store.Open("ReadWrite")
    $store.Add($cert)
    $store.Close()
    Write-Host "[SUCCESS] CogniShift Demo CA installed into Cert:\CurrentUser\Root." -ForegroundColor Green
    Write-Host "Subject: $($cert.Subject)" -ForegroundColor Gray
    Write-Host "Thumbprint: $($cert.Thumbprint)" -ForegroundColor Gray
} catch {
    Write-Error "Failed to install CA certificate: $_"
    exit 1
}
