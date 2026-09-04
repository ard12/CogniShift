<#
.SYNOPSIS
    CogniShift Phase 6 - Automated Elevated Reality Check Script.
.DESCRIPTION
    Must be executed in an elevated (Administrator) PowerShell terminal.
    Executes empirical tests for:
      1. Windows Defender Firewall rule targeting, enablement, idempotency, loopback, public block, LAN block.
      2. Disable firewall control comparison test (proving causality).
      3. OS-level independent observer trace (pktmon).
      4. Safe firewall teardown and idempotency check.
      5. Generates machine-readable evidence in artifacts/phase6_firewall_final/.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CogniShift Phase 6 - Elevated Reality Check & Evidence" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Administrator Check
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "[FATAL] Administrator privileges required. Please open PowerShell as Administrator and rerun."
    exit 1
}
Write-Host "[OK] Elevated Administrator session confirmed." -ForegroundColor Green

# 2. Resolve Python Executable
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($PythonCmd) {
    $PythonExe = $PythonCmd.Source
} else {
    $PythonExe = "C:\Users\sitan\AppData\Local\Programs\Python\Python312\python.exe"
}
Write-Host "[OK] Target CogniShift Python: $PythonExe" -ForegroundColor Green

$ArtifactsDir = Join-Path $PSScriptRoot "..\artifacts\phase6_firewall_final"
if (-not (Test-Path $ArtifactsDir)) {
    New-Item -ItemType Directory -Path $ArtifactsDir -Force | Out-Null
}

# 3. Record Initial State
Write-Host "`n[STEP 1] Recording firewall state before enable..." -ForegroundColor Cyan
$beforeCount = (Get-NetFirewallRule).Count
$beforeCogni = Get-NetFirewallRule -Group "CogniShift-Phase6" -ErrorAction SilentlyContinue
$beforeText = @"
Firewall State Before Enable
Timestamp: $(Get-Date -Format o)
Total NetFirewallRule Count: $beforeCount
CogniShift-Phase6 Rules: $(if ($beforeCogni) { ($beforeCogni | Format-Table DisplayName, Enabled, Direction, Action, Profile | Out-String) } else { "NONE (0 rules found)" })
"@
$beforeText | Out-File -FilePath (Join-Path $ArtifactsDir "firewall_before.txt") -Encoding utf8

# 4. Enable Strict Firewall Rules
Write-Host "`n[STEP 2] Enabling CogniShift strict firewall rules..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "enable_strict_network_policy.ps1") -PythonPath $PythonExe

# 5. Inspect Enabled Rules
Write-Host "`n[STEP 3] Inspecting active CogniShift firewall rules..." -ForegroundColor Cyan
$enabledRules = Get-NetFirewallRule -Group "CogniShift-Phase6"
$enabledText = @"
Firewall State Enabled
Timestamp: $(Get-Date -Format o)
Total NetFirewallRule Count: $((Get-NetFirewallRule).Count)
CogniShift Rule Count: $($enabledRules.Count)

Rules Detail:
$($enabledRules | Format-List DisplayName, Enabled, Direction, Action, Profile | Out-String)

Address Filters:
$(Get-NetFirewallAddressFilter -AssociatedNetFirewallRule $enabledRules | Format-List * | Out-String)

Application Filters:
$(Get-NetFirewallApplicationFilter -AssociatedNetFirewallRule $enabledRules | Format-List * | Out-String)
"@
$enabledText | Out-File -FilePath (Join-Path $ArtifactsDir "firewall_enabled.txt") -Encoding utf8

# 6. Enable Script Idempotency
Write-Host "`n[STEP 4] Testing enable script idempotency..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "enable_strict_network_policy.ps1") -PythonPath $PythonExe
$secondEnableRules = Get-NetFirewallRule -Group "CogniShift-Phase6"
Write-Host "Rule count after 1st enable: $($enabledRules.Count), after 2nd enable: $($secondEnableRules.Count)" -ForegroundColor Gray

# 7. OS Firewall Test - Loopback
Write-Host "`n[STEP 5] Testing raw socket loopback (127.0.0.1:11434)..." -ForegroundColor Cyan
& $PythonExe (Join-Path $PSScriptRoot "test_os_firewall_sockets.py") `
    --target-host "127.0.0.1" --target-port 11434 `
    --output-json (Join-Path $ArtifactsDir "firewall_loopback_test.json")

# 8. OS Firewall Test - Public Destination (Should be blocked by OS)
Write-Host "`n[STEP 6] Testing raw socket public destination (1.1.1.1:80)..." -ForegroundColor Cyan
& $PythonExe (Join-Path $PSScriptRoot "test_os_firewall_sockets.py") `
    --target-host "1.1.1.1" --target-port 80 `
    --output-json (Join-Path $ArtifactsDir "firewall_public_test.json")

# 9. OS Firewall Test - Private LAN Destination (Should be blocked by OS)
Write-Host "`n[STEP 7] Testing raw socket unauthorized private LAN (192.168.1.254:80)..." -ForegroundColor Cyan
& $PythonExe (Join-Path $PSScriptRoot "test_os_firewall_sockets.py") `
    --target-host "192.168.1.254" --target-port 80 `
    --output-json (Join-Path $ArtifactsDir "firewall_private_test.json")

# 10. Control Test with Firewall Disabled
Write-Host "`n[STEP 8] Disabling firewall to test control public connection..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1")
Write-Host "Executing public control socket (1.1.1.1:80) with firewall disabled..." -ForegroundColor Gray
& $PythonExe (Join-Path $PSScriptRoot "test_os_firewall_sockets.py") `
    --target-host "1.1.1.1" --target-port 80 `
    --output-json (Join-Path $ArtifactsDir "firewall_public_control_test.json")

# 11. Independent OS-Level Observation with PktMon
Write-Host "`n[STEP 9] Re-enabling strict firewall for OS packet trace (pktmon)..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "enable_strict_network_policy.ps1") -PythonPath $PythonExe

$etlPath = Join-Path $ArtifactsDir "os_trace.etl"
$txtTracePath = Join-Path $ArtifactsDir "os_trace.txt"
$setupPath = Join-Path $ArtifactsDir "os_observer_setup.txt"

Write-Host "Configuring pktmon capture..." -ForegroundColor Gray
pktmon filter remove 2>$null | Out-Null
pktmon filter add -p 11434 2>$null | Out-Null

$obsStartTime = (Get-Date -Format o)
pktmon start --capture --pkt-size 128 -f $etlPath 2>$null | Out-Null

@"
Observer Tool: Windows PktMon (Packet Monitor)
Start Timestamp: $obsStartTime
ETL Output: $etlPath
Filter: Port 11434 (Loopback inference traffic)
"@ | Out-File -FilePath $setupPath -Encoding utf8

# Negative control against loopback
Write-Host "Generating negative control traffic under pktmon..." -ForegroundColor Gray
& $PythonExe (Join-Path $PSScriptRoot "test_os_firewall_sockets.py") `
    --target-host "127.0.0.1" --target-port 11434 `
    --output-json (Join-Path $ArtifactsDir "os_observer_negative_control.json")

pktmon stop 2>$null | Out-Null
$obsStopTime = (Get-Date -Format o)
"Stop Timestamp: $obsStopTime" | Out-File -FilePath $setupPath -Append -Encoding utf8

Write-Host "Converting pktmon ETL trace to text format..." -ForegroundColor Gray
pktmon etl2txt $etlPath -o $txtTracePath 2>$null | Out-Null

# 12. Final Teardown
Write-Host "`n[STEP 10] Disabling firewall rules and verifying clean teardown..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1")
$afterRules = Get-NetFirewallRule -Group "CogniShift-Phase6" -ErrorAction SilentlyContinue
$afterCount = (Get-NetFirewallRule).Count
$afterText = @"
Firewall State After Teardown
Timestamp: $(Get-Date -Format o)
Total NetFirewallRule Count: $afterCount
Remaining CogniShift-Phase6 Rules: $(if ($afterRules) { $afterRules.Count } else { 0 })
"@
$afterText | Out-File -FilePath (Join-Path $ArtifactsDir "firewall_after.txt") -Encoding utf8

# Disable Idempotency
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1")

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  Empirical Verification Execution Complete!" -ForegroundColor Green
Write-Host "  Artifacts recorded in: $ArtifactsDir" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
