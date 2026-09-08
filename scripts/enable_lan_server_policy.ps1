# Configure Windows Defender Firewall for CogniShift LAN Server
# Restricts Port 8443 to the authorized team terminals only.
$ErrorActionPreference = "Stop"

$AllowedRemoteIPs = "10.10.163.208,10.10.163.213,10.10.144.247,10.10.164.63,10.10.145.22,127.0.0.1,10.10.182.228"
$GroupName = "CogniShift-LAN-Server"

Write-Host "Enabling Firewall Policy for $GroupName..." -ForegroundColor Cyan

# Remove old rules if existing
Remove-NetFirewallRule -Group $GroupName -ErrorAction SilentlyContinue

# Inbound: Port 8443 from team IPs only
New-NetFirewallRule -DisplayName "CogniShift LAN Server (HTTPS 8443 Inbound)" `
    -Group $GroupName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort 8443 `
    -RemoteAddress $AllowedRemoteIPs.Split(",") `
    -Profile Any

Write-Host "[SUCCESS] Inbound rule created: Port 8443 allowed only from team IPs." -ForegroundColor Green
Write-Host "Allowed IPs: $AllowedRemoteIPs" -ForegroundColor Gray
