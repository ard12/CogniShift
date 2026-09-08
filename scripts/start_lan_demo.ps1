# Launch CogniShift LAN Server on 0.0.0.0:8443 with TLS
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

Write-Host "=== STARTING COGNISHIFT LAN SECURE SERVER ===" -ForegroundColor Cyan

# 1. Ensure certificates exist
Write-Host "Checking TLS certificates..." -ForegroundColor Gray
python scripts\generate_local_tls.py

# 2. Ensure team auth is ready
Write-Host "Checking team demo auth store..." -ForegroundColor Gray
python scripts\bootstrap_team_demo_auth.py

$CertFile = "data/certs/server_cert.pem"
$KeyFile  = "data/certs/server_key.pem"

if (-not (Test-Path $CertFile) -or -not (Test-Path $KeyFile)) {
    Write-Error "SSL certificate or key missing in data/certs/"
    exit 1
}

Write-Host "`n[STARTING UVICORN SERVER]" -ForegroundColor Green
Write-Host "Listening on: https://0.0.0.0:8443 (LAN IP: https://10.10.182.228:8443)" -ForegroundColor Yellow
Write-Host "Sovereign Mode: LOCAL (Zero Cloud Egress)" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to terminate.`n" -ForegroundColor Gray

python -m uvicorn cognishift.app.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile $KeyFile --ssl-certfile $CertFile
