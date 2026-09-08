# Disable/Remove Windows Defender Firewall rules for CogniShift LAN Server
$ErrorActionPreference = "SilentlyContinue"

$GroupName = "CogniShift-LAN-Server"
Write-Host "Removing Firewall rules for group $GroupName..." -ForegroundColor Yellow
Remove-NetFirewallRule -Group $GroupName
Write-Host "[SUCCESS] Firewall rules removed." -ForegroundColor Green
