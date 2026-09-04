<#
.SYNOPSIS
    Enables CogniShift Phase 6 Strict Network Policy via Windows Defender Firewall.
.DESCRIPTION
    Creates process-scoped firewall rules under group 'CogniShift-Phase6' targeting
    the CogniShift Python executable. Restricts all outbound communication to loopback
    (127.0.0.1, ::1) and allows inbound loopback on port 8000.
    Requires Administrator privileges.
.PARAMETER PythonPath
    Optional path to the Python executable. If omitted, automatically resolves 'python'.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$PythonPath = ""
)

# 1. Administrator Privilege Check
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Administrator privileges required. Please run PowerShell as Administrator to configure Windows Defender Firewall."
    exit 1
}

# 2. Resolve Python Executable
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCmd) {
        $PythonPath = $PythonCmd.Source
    } else {
        $PythonPath = "C:\Users\sitan\AppData\Local\Programs\Python\Python312\python.exe"
    }
}

if (-not (Test-Path $PythonPath)) {
    Write-Error "Target Python executable not found at '$PythonPath'."
    exit 1
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CogniShift Phase 6 - Strict Network Policy Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Target Executable: $PythonPath" -ForegroundColor Yellow
Write-Host "Rule Group:        CogniShift-Phase6" -ForegroundColor Yellow
Write-Host ""

# 3. Idempotent Cleanup: Remove existing CogniShift-Phase6 rules
Write-Host "Cleaning up existing CogniShift-Phase6 rules..." -ForegroundColor Gray
Remove-NetFirewallRule -Group "CogniShift-Phase6" -ErrorAction SilentlyContinue

# 4. Create Rule: Allow Outbound Loopback (IPv4 & IPv6)
Write-Host "Creating Rule: Allow Outbound Loopback..." -ForegroundColor Green
New-NetFirewallRule -DisplayName "CogniShift-Phase6-Allow-Loopback-Out" `
    -Group "CogniShift-Phase6" `
    -Description "Allow CogniShift Python process outbound loopback communication" `
    -Direction Outbound `
    -Program $PythonPath `
    -RemoteAddress @("127.0.0.1", "::1") `
    -Action Allow `
    -Profile Any `
    -Enabled True | Out-Null

# 5. Create Rule: Allow Inbound Loopback on Port 8000 (FastAPI)
Write-Host "Creating Rule: Allow Inbound Loopback (Port 8000)..." -ForegroundColor Green
New-NetFirewallRule -DisplayName "CogniShift-Phase6-Allow-Loopback-In" `
    -Group "CogniShift-Phase6" `
    -Description "Allow inbound loopback traffic to CogniShift on port 8000" `
    -Direction Inbound `
    -Program $PythonPath `
    -LocalPort 8000 `
    -Protocol TCP `
    -RemoteAddress @("127.0.0.1", "::1") `
    -Action Allow `
    -Profile Any `
    -Enabled True | Out-Null

# 6. Create Rule: Block Outbound Non-Loopback (WAN/LAN egress)
Write-Host "Creating Rule: Block Outbound WAN/LAN..." -ForegroundColor Yellow
New-NetFirewallRule -DisplayName "CogniShift-Phase6-Block-Outbound-WAN" `
    -Group "CogniShift-Phase6" `
    -Description "Block all outbound non-loopback network egress for CogniShift Python process" `
    -Direction Outbound `
    -Program $PythonPath `
    -RemoteAddress @("0.0.0.0-126.255.255.255", "128.0.0.0-255.255.255.255", "::-::0", "::2-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff") `
    -Action Block `
    -Profile Any `
    -Enabled True | Out-Null

Write-Host ""
Write-Host "SUCCESS: CogniShift Phase 6 Strict Network Policy is active." -ForegroundColor Green
Write-Host "Outbound non-loopback network egress is blocked at OS level for: $PythonPath" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
