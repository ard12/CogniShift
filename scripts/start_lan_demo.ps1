param(
    [switch]$RestartExisting
)

# Launch CogniShift LAN Server on 0.0.0.0:8443 with TLS
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

Write-Host "=== STARTING COGNISHIFT LAN SECURE SERVER ===" -ForegroundColor Cyan

# 0. Check if port 8443 is already listening
$port = 8443
$occupied = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' } | Select-Object -First 1

if ($occupied) {
    $occupiedPid = $occupied.OwningProcess
    $proc = Get-Process -Id $occupiedPid -ErrorAction SilentlyContinue
    $procName = if ($proc) { $proc.ProcessName } else { "Unknown" }
    $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $occupiedPid" -ErrorAction SilentlyContinue
    $cmdLine = if ($cim) { $cim.CommandLine } else { "Unknown" }

    Write-Host "`n[PORT $port ALREADY IN USE]" -ForegroundColor Red
    Write-Host "PID:          $occupiedPid" -ForegroundColor Yellow
    Write-Host "PROCESS:      $procName" -ForegroundColor Yellow
    Write-Host "COMMAND LINE: $cmdLine" -ForegroundColor Gray

    $isCogniShift = ($cmdLine -like "*cognishift.app.main:app*")

    if ($isCogniShift) {
        Write-Host "`nCogniShift appears to already be running." -ForegroundColor Yellow
        if ($RestartExisting) {
            Write-Host "[-RestartExisting specified] Safely terminating PID $occupiedPid..." -ForegroundColor Cyan
            Stop-Process -Id $occupiedPid -Force
            Start-Sleep -Seconds 2
            Write-Host "Prior instance stopped cleanly." -ForegroundColor Green
        } else {
            Write-Host "To restart with latest code:  .\scripts\start_lan_demo.ps1 -RestartExisting" -ForegroundColor Cyan
            Write-Host "To view active dashboard:     https://localhost:8443" -ForegroundColor Green
            Write-Host "Exiting safely without launching duplicate server.`n" -ForegroundColor Yellow
            exit 0
        }
    } else {
        Write-Error "Port $port is in use by an unrecognized non-CogniShift process (PID $occupiedPid). Please terminate it manually."
        exit 1
    }
}

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
Write-Host "Client CA Certificate: data/certs/cognishift_demo_ca.crt (Distribute to team browsers)" -ForegroundColor Cyan
Write-Host "Client Auth Tokens:    data/private/team_tokens_summary.txt (Gitignored)" -ForegroundColor Cyan
Write-Host "Sovereign Mode:        LOCAL (CogniShift Public Egress: BLOCKED)" -ForegroundColor Green
Write-Host "Press Ctrl+C to terminate.`n" -ForegroundColor Gray

python -m uvicorn cognishift.app.main:app --app-dir src --host 0.0.0.0 --port 8443 --ssl-keyfile $KeyFile --ssl-certfile $CertFile
