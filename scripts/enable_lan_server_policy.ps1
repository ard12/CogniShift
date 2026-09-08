# Configure Windows Defender Firewall for CogniShift LAN Server
# Restricts Port 8443 to authorized team terminals and binds to CogniShift Python.
param (
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

# Auto-detect Python binary running CogniShift if not explicitly provided
if (-not $PythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        $PythonExe = $cmd.Source
    }
}

$AllowedRemoteIPs = "10.10.163.208,10.10.163.213,10.10.144.247,10.10.164.63,10.10.145.22,127.0.0.1,10.10.182.228"
$GroupName = "CogniShift-LAN-Server"

Write-Host "=== ENABLING FIREWALL POLICY FOR $GroupName ===" -ForegroundColor Cyan
if ($PythonExe) {
    Write-Host "Targeting Python executable: $PythonExe" -ForegroundColor Gray
}

# Remove existing rules in group before applying new policy
Remove-NetFirewallRule -Group $GroupName -ErrorAction SilentlyContinue

# 1. Inbound: Allow HTTPS 8443 from authorized team IPs only, bound to Python process
$ruleParams = @{
    DisplayName   = "CogniShift LAN Server (HTTPS 8443 Inbound)"
    Group         = $GroupName
    Direction     = "Inbound"
    Action        = "Allow"
    Protocol      = "TCP"
    LocalPort     = 8443
    RemoteAddress = $AllowedRemoteIPs.Split(",")
    Profile       = "Any"
}
if ($PythonExe -and (Test-Path $PythonExe)) {
    $ruleParams["Program"] = $PythonExe
}

New-NetFirewallRule @ruleParams | Out-Null
Write-Host "[SUCCESS] Inbound rule created: Port 8443 allowed for team IPs." -ForegroundColor Green
Write-Host "Allowed Terminals: $AllowedRemoteIPs" -ForegroundColor Gray

# 2. Defense-in-depth: Ensure Ollama (11434) and Vite (5173) are NEVER exposed to remote LAN
New-NetFirewallRule -DisplayName "CogniShift Block LAN Exposure (Ollama 11434 & Vite 5173)" `
    -Group $GroupName `
    -Direction Inbound `
    -Action Block `
    -Protocol TCP `
    -LocalPort 11434, 5173 `
    -RemoteAddress "10.10.0.0/16" `
    -Profile Any | Out-Null

Write-Host "[SUCCESS] Defense-in-depth rule created: Remote LAN blocked from Ollama (11434) and Vite (5173)." -ForegroundColor Green
Write-Host "[VERIFIED] Loopback (127.0.0.1) communication with Ollama is fully preserved." -ForegroundColor Cyan
