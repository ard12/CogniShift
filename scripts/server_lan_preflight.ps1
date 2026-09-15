# Server LAN Preflight Diagnostics
$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

Write-Host "=== COGNISHIFT SERVER LAN PREFLIGHT CHECK ===" -ForegroundColor Cyan

# 1. Check Python & virtual environment
$pythonVer = python --version 2>&1
Write-Host "[1] Python Version: $pythonVer" -ForegroundColor Green

# 2. Check TLS Certificates
$caCert = "data/certs/cognishift_demo_ca.crt"
$srvCert = "data/certs/server_cert.pem"
$srvKey = "data/certs/server_key.pem"
if ((Test-Path $caCert) -and (Test-Path $srvCert) -and (Test-Path $srvKey)) {
    Write-Host "[2] TLS Certificates: PRESENT" -ForegroundColor Green
} else {
    Write-Host "[2] TLS Certificates: MISSING (Run scripts\generate_local_tls.py)" -ForegroundColor Red
}

# 3. Check Ollama Service
try {
    $ollama = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
    $models = ($ollama.models | ForEach-Object { $_.name }) -join ", "
    Write-Host "[3] Local Ollama: ACTIVE (Models: $models)" -ForegroundColor Green
} catch {
    Write-Host "[3] Local Ollama: NOT REACHABLE on http://127.0.0.1:11434" -ForegroundColor Red
}

# 4. Check Team Auth Store
$authStore = "data/private/auth_store.json"
if (Test-Path $authStore) {
    Write-Host "[4] Team Auth Store: PRESENT ($authStore)" -ForegroundColor Green
} else {
    Write-Host "[4] Team Auth Store: MISSING (Run scripts\bootstrap_team_demo_auth.py)" -ForegroundColor Yellow
}

# 5. Show current active LAN/hotspot addresses (DHCP addresses may change).
$ipConfig = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and
        $_.AddressState -eq 'Preferred' -and
        $_.InterfaceAlias -notmatch 'vEthernet|Loopback'
    } |
    Select-Object -ExpandProperty IPAddress -Unique)
if ($ipConfig.Count -gt 0) {
    Write-Host "[5] Active LAN URLs:" -ForegroundColor Cyan
    foreach ($ip in $ipConfig) {
        Write-Host "    -> https://${ip}:8443" -ForegroundColor Cyan
    }
} else {
    Write-Host "[5] Active LAN URL: NONE (connect to hotspot/LAN and retry)" -ForegroundColor Yellow
}

Write-Host "`n=== PREFLIGHT COMPLETE ===" -ForegroundColor Cyan
