param(
    [switch]$RestartExisting
)

# Launch CogniShift on every local adapter with certificate SANs that track
# addresses currently assigned by DHCP, including phone hotspots.
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot
$PythonExe = (Get-Command python -ErrorAction Stop).Source

if (-not (Test-Path "frontend\dist\index.html")) {
    Write-Host "Frontend production bundle not found in frontend/dist. Building Vite UI..." -ForegroundColor Yellow
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        npm --prefix frontend run build
    } else {
        Write-Host "WARNING: 'npm' not found in PATH. Please run 'npm run build' in frontend/ to serve the UI." -ForegroundColor Yellow
    }
}

Write-Host "=== STARTING COGNISHIFT LAN SECURE SERVER ===" -ForegroundColor Cyan

$port = 8443
$occupied = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq 'Listen' } |
    Select-Object -First 1

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

    if ($cmdLine -notlike "*cognishift.app.main:app*" -and $cmdLine -notlike "*run_tls_server*") {
        Write-Error "Port $port is in use by an unrecognized process. Terminate it manually."
        exit 1
    }
    if (-not $RestartExisting) {
        Write-Host "CogniShift is already running. Use -RestartExisting to reload it." -ForegroundColor Yellow
        Write-Host "Host URL: https://127.0.0.1:8443" -ForegroundColor Green
        exit 0
    }
    Write-Host "Restarting the existing CogniShift process..." -ForegroundColor Cyan
    Stop-Process -Id $occupiedPid -Force
    Start-Sleep -Seconds 2
}

$activeIps = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and
        $_.AddressState -eq 'Preferred' -and
        $_.InterfaceAlias -notmatch 'vEthernet|Loopback'
    } |
    Select-Object -ExpandProperty IPAddress -Unique)

Write-Host "Syncing TLS certificates with active network IPs..." -ForegroundColor Gray
$tlsArgs = @("scripts\generate_local_tls.py", "--ip", "127.0.0.1")
foreach ($ip in $activeIps) {
    $tlsArgs += @("--ip", $ip)
}
& $PythonExe @tlsArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "TLS certificate synchronization failed."
    exit 1
}

Write-Host "Checking team demo auth store..." -ForegroundColor Gray
& $PythonExe scripts\bootstrap_team_demo_auth.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Team demo authentication bootstrap failed."
    exit 1
}

$CertFile = (Resolve-Path "data/certs/server_cert.pem").Path
$KeyFile = (Resolve-Path "data/certs/server_key.pem").Path
if (-not (Test-Path $CertFile) -or -not (Test-Path $KeyFile)) {
    Write-Error "SSL certificate or key missing in data/certs/."
    exit 1
}

Write-Host "`n======================================================================" -ForegroundColor Cyan
Write-Host "     COGNISHIFT AIR-GAPPED SECURE SERVER (PORT 8443 HTTPS)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " [HOST LAPTOP]" -ForegroundColor Green
Write-Host "   -> https://127.0.0.1:8443  (Recommended; bypasses DNS)" -ForegroundColor Green
Write-Host "   -> https://localhost:8443" -ForegroundColor Gray
Write-Host "`n [OTHER LAPTOPS ON THE SAME HOTSPOT / LAN]" -ForegroundColor Yellow
if ($activeIps.Count -gt 0) {
    foreach ($ip in $activeIps) {
        Write-Host "   -> https://${ip}:8443" -ForegroundColor Yellow
    }
} else {
    Write-Host "   -> No active LAN adapter detected. Connect to the hotspot, then relaunch." -ForegroundColor Red
}
Write-Host "`n [BROWSER ACCESS]" -ForegroundColor Gray
Write-Host "   Include https:// in the address." -ForegroundColor Gray
Write-Host "   If prompted, trust the CogniShift demo CA or use Advanced -> Proceed." -ForegroundColor Gray
Write-Host "======================================================================`n" -ForegroundColor Cyan
Write-Host "Client CA Certificate: data/certs/cognishift_demo_ca.crt" -ForegroundColor Cyan
Write-Host "Client Auth Tokens:    data/private/team_tokens_summary.txt (Gitignored)" -ForegroundColor Cyan
Write-Host "Sovereign Mode:        LOCAL (CogniShift Public Egress: BLOCKED)" -ForegroundColor Green
Write-Host "Press Ctrl+C to terminate.`n" -ForegroundColor Gray

# Keep the delay helper hidden; its final browser window is intentionally visible.
Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-Command",
    "Start-Sleep -Seconds 2; Start-Process 'https://127.0.0.1:8443'"
)

& $PythonExe scripts\run_tls_server.py --host 0.0.0.0 --port 8443 --ssl-keyfile $KeyFile --ssl-certfile $CertFile
