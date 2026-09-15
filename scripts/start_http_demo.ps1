param(
    [switch]$RestartExisting
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

$port = 8000
$occupied = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq 'Listen' } |
    Select-Object -First 1

if ($occupied) {
    $occupiedPid = $occupied.OwningProcess
    $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $occupiedPid" -ErrorAction SilentlyContinue
    $cmdLine = if ($cim) { $cim.CommandLine } else { "" }
    if ($cmdLine -notlike "*cognishift.app.main:app*") {
        Write-Error "Port $port belongs to an unrecognized process (PID $occupiedPid)."
        exit 1
    }
    if (-not $RestartExisting) {
        Write-Host "CogniShift is already running on http://127.0.0.1:$port" -ForegroundColor Yellow
        exit 0
    }
    Write-Host "Restarting the existing CogniShift HTTP process (PID $occupiedPid)..." -ForegroundColor Yellow
    Stop-Process -Id $occupiedPid -Force
    Start-Sleep -Seconds 2
}

Write-Host "Checking team demo auth store..." -ForegroundColor Gray
python scripts\bootstrap_team_demo_auth.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Team demo authentication bootstrap failed."
    exit 1
}

Write-Host "`n======================================================================" -ForegroundColor Cyan
Write-Host " COGNISHIFT HTTP FALLBACK (PORT 8000 - THIS LAPTOP ONLY)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   -> http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "   -> http://localhost:8000" -ForegroundColor Gray
Write-Host " Remote laptops must use HTTPS 8443 so WebCrypto trusted-device" -ForegroundColor Yellow
Write-Host " verification remains available." -ForegroundColor Yellow
Write-Host "======================================================================`n" -ForegroundColor Cyan

Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-Command",
    "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000'"
)

python -m uvicorn cognishift.app.main:app --app-dir src --host 127.0.0.1 --port 8000
