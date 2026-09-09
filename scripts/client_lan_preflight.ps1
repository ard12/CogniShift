# Client LAN Preflight Diagnostics (Run on client laptops)
param(
    [Parameter(Mandatory = $true)]
    [string]$ServerHost
)

$ErrorActionPreference = "Continue"
Write-Host "=== COGNISHIFT CLIENT LAN PREFLIGHT CHECK ===" -ForegroundColor Cyan
Write-Host "Target Server: https://$ServerHost" -ForegroundColor Yellow

# 1. Test Network Reachability
$hostOnly = $ServerHost.Split(":")[0]
$portOnly = [int]$ServerHost.Split(":")[1]
Write-Host "[1] Testing TCP Reachability to $hostOnly on port $portOnly..." -ForegroundColor Gray
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $iar = $tcp.BeginConnect($hostOnly, $portOnly, $null, $null)
    $wait = $iar.AsyncWaitHandle.WaitOne(3000, $false)
    if ($wait) {
        $tcp.EndConnect($iar)
        $tcp.Close()
        Write-Host "    -> TCP Reachable!" -ForegroundColor Green
    } else {
        $tcp.Close()
        Write-Host "    -> TCP CONNECTION TIMED OUT (Check Firewall or Wi-Fi IP)" -ForegroundColor Red
    }
} catch {
    Write-Host "    -> TCP Connection Failed: $_" -ForegroundColor Red
}

# 2. Test HTTPS API Request
Write-Host "[2] Testing HTTPS API /api/v1/auth/demo-status..." -ForegroundColor Gray
try {
    $res = Invoke-RestMethod -Uri "https://$ServerHost/api/v1/auth/demo-status" -TimeoutSec 5
    Write-Host "    -> HTTPS API Reachable! Response: $($res | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "    -> HTTPS Request Failed: $_" -ForegroundColor Yellow
    Write-Host "       If certificate error, install data/certs/cognishift_demo_ca.crt using scripts/install_cognishift_demo_ca.ps1" -ForegroundColor Gray
}

Write-Host "`n=== CLIENT PREFLIGHT FINISHED ===" -ForegroundColor Cyan
