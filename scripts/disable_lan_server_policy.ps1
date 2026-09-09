# Disable/Remove Windows Defender Firewall rules for CogniShift LAN Server
$ErrorActionPreference = "SilentlyContinue"

$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "`n[PERMISSION DENIED] Administrator privileges are required to modify Windows Defender Firewall." -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator or execute with elevated privileges.`n" -ForegroundColor Yellow
    exit 1
}

$GroupName = "CogniShift-LAN-Server"
Write-Host "Removing Firewall rules for group $GroupName..." -ForegroundColor Yellow
Remove-NetFirewallRule -Group $GroupName -ErrorAction SilentlyContinue
Write-Host "[SUCCESS] Firewall rules removed." -ForegroundColor Green
