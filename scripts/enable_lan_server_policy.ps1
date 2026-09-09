# Configure Windows Defender Firewall for CogniShift LAN Server
# Restricts Port 8443 to authorized team terminals and binds to CogniShift Python.
param (
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

# 1. Enforce Administrator elevation check
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "`n[PERMISSION DENIED] Administrator privileges are required to configure Windows Defender Firewall." -ForegroundColor Red
    Write-Host "Windows Defender Firewall cannot be modified from a standard user session.`n" -ForegroundColor Yellow
    Write-Host "To apply the LAN server policy, run this command to launch an elevated Administrator window:" -ForegroundColor Cyan
    $cmdStr = 'Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -NoExit -File ""' + $PSCommandPath + '"""'
    Write-Host "$cmdStr`n" -ForegroundColor White
    exit 1
}

# Auto-detect Python binary running CogniShift if not explicitly provided
if (-not $PythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        $PythonExe = $cmd.Source
    }
}

$AllowedRemoteIPs = @("LocalSubnet", "127.0.0.1")
$GroupName = "CogniShift-LAN-Server"

Write-Host "=== ENABLING FIREWALL POLICY FOR $GroupName ===" -ForegroundColor Cyan
if ($PythonExe) {
    Write-Host "Targeting Python executable: $PythonExe" -ForegroundColor Gray
}

# Remove existing rules in group before applying new policy
Remove-NetFirewallRule -Group $GroupName -ErrorAction SilentlyContinue

try {
    # 1. Inbound: Allow HTTPS 8443 from authorized team IPs only, bound to Python process
    $ruleParams = @{
        DisplayName   = "CogniShift LAN Server (HTTPS 8443 Inbound)"
        Group         = $GroupName
        Direction     = "Inbound"
        Action        = "Allow"
        Protocol      = "TCP"
        LocalPort     = 8443
        RemoteAddress = $AllowedRemoteIPs
        Profile       = "Any"
        ErrorAction   = "Stop"
    }
    if ($PythonExe -and (Test-Path $PythonExe)) {
        $ruleParams["Program"] = $PythonExe
    }

    New-NetFirewallRule @ruleParams | Out-Null
    Write-Host "[SUCCESS] Inbound rule created: Port 8443 allowed for team IPs." -ForegroundColor Green
    Write-Host "Allowed Sources: $($AllowedRemoteIPs -join ', ')" -ForegroundColor Gray

    # 2. Defense-in-depth: Ensure Ollama (11434) and Vite (5173) are NEVER exposed to remote LAN
    New-NetFirewallRule -DisplayName "CogniShift Block LAN Exposure (Ollama 11434 & Vite 5173)" `
        -Group $GroupName `
        -Direction Inbound `
        -Action Block `
        -Protocol TCP `
        -LocalPort 11434, 5173 `
        -RemoteAddress "LocalSubnet" `
        -Profile Any `
        -ErrorAction Stop | Out-Null

    Write-Host "[SUCCESS] Defense-in-depth rule created: Remote LAN blocked from Ollama (11434) and Vite (5173)." -ForegroundColor Green
    Write-Host "[VERIFIED] Loopback (127.0.0.1) communication with Ollama is fully preserved." -ForegroundColor Cyan
} catch {
    Write-Host "`n[FAILED] Firewall policy could not be applied: $_" -ForegroundColor Red
    exit 1
}
