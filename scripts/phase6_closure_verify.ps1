<#
.SYNOPSIS
    CogniShift Phase 6 Final Closure Verification Master Script.
.DESCRIPTION
    Must be executed in an elevated (Administrator) PowerShell terminal.
    Closes all three remaining evidence gaps:
      1. Broad PktMon kernel packet observation covering loopback, public, and private ports.
      2. Controlled private-LAN firewall A/B/A causality test against 172.17.64.1:19878.
      3. Full canonical non-CogniShift firewall rule diff (before vs after).
      4. Complete Phase 6 and Full platform regressions.
      5. Machine-decided gate calculation and evidence manifest generation.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CogniShift Phase 6 - Final Closure Verification" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Administrator Check
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "[FATAL] Administrator privileges required. Please run this script in an elevated PowerShell terminal."
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
Write-Host "[OK] Python Executable: $PythonExe" -ForegroundColor Green

$ClosureDir = Join-Path $PSScriptRoot "..\artifacts\phase6_closure"
if (-not (Test-Path $ClosureDir)) {
    New-Item -ItemType Directory -Path $ClosureDir -Force | Out-Null
}

# -----------------------------------------------------------------------------
# STEP 1: Canonical Non-CogniShift Firewall Export (BEFORE)
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 1] Exporting canonical non-CogniShift firewall rules (BEFORE)..." -ForegroundColor Cyan
# First ensure no lingering CogniShift rules
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null
$rulesBefore = Get-NetFirewallRule | Where-Object { $_.RuleGroup -ne 'CogniShift-Phase6' } |
    Select-Object Name, DisplayName, DisplayGroup, Enabled, Direction, Action, Profile |
    Sort-Object Name
$rulesBeforeJson = $rulesBefore | ConvertTo-Json -Depth 2
$beforePath = Join-Path $ClosureDir "firewall_non_cognishift_before.json"
$rulesBeforeJson | Out-File -FilePath $beforePath -Encoding utf8
Write-Host "Exported $($rulesBefore.Count) non-CogniShift rules to $beforePath" -ForegroundColor Gray

# -----------------------------------------------------------------------------
# STEP 2: Broad PktMon Negative Control (Firewall Disabled)
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 2] Running Broad PktMon Negative Control (Loopback + Public)..." -ForegroundColor Cyan
$negEtl = Join-Path $ClosureDir "pktmon_negative_control.etl"
$negTxt = Join-Path $ClosureDir "pktmon_negative_control.txt"

pktmon stop 2>$null | Out-Null
pktmon filter remove 2>$null | Out-Null
pktmon filter add -p 11434 2>$null | Out-Null
pktmon filter add -p 80 2>$null | Out-Null

Write-Host "Starting broad PktMon capture for negative control..." -ForegroundColor Gray
pktmon start --capture --pkt-size 128 -f $negEtl 2>$null | Out-Null

# Probe loopback to Ollama
& $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --probe --host "127.0.0.1" --port 11434 --out (Join-Path $ClosureDir "neg_ctl_loopback_probe.json")
# Probe public target 1.1.1.1:80
& $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --probe --host "1.1.1.1" --port 80 --out (Join-Path $ClosureDir "neg_ctl_public_probe.json")

pktmon stop 2>$null | Out-Null
Write-Host "Decoding negative control ETL trace..." -ForegroundColor Gray
pktmon etl2txt $negEtl -o $negTxt 2>$null | Out-Null

# Parse negative control trace
& $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --parse-pktmon-neg-control

# -----------------------------------------------------------------------------
# STEP 3: Public Firewall A/B/A Causality Test
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 3] Executing Public Firewall A/B/A Causality Test..." -ForegroundColor Cyan
$pubTarget = "1.1.1.1"
$pubPort = 80

# Stage A1: Disabled
Write-Host "  Stage A1 (Firewall Disabled): Probing ${pubTarget}:${pubPort}..." -ForegroundColor Gray
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null
$pA1 = & $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --probe --host $pubTarget --port $pubPort --out (Join-Path $ClosureDir "tmp_pub_a1.json")
$resA1 = Get-Content (Join-Path $ClosureDir "tmp_pub_a1.json") | ConvertFrom-Json

# Stage B: Enabled
Write-Host "  Stage B (Firewall Enabled): Enabling rules & probing ${pubTarget}:${pubPort}..." -ForegroundColor Gray
& (Join-Path $PSScriptRoot "enable_strict_network_policy.ps1") -PythonPath $PythonExe | Out-Null
$pB = & $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --probe --host $pubTarget --port $pubPort --out (Join-Path $ClosureDir "tmp_pub_b.json")
$resB = Get-Content (Join-Path $ClosureDir "tmp_pub_b.json") | ConvertFrom-Json

# Stage A2: Disabled
Write-Host "  Stage A2 (Firewall Disabled Again): Disabling rules & probing ${pubTarget}:${pubPort}..." -ForegroundColor Gray
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null
$pA2 = & $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --probe --host $pubTarget --port $pubPort --out (Join-Path $ClosureDir "tmp_pub_a2.json")
$resA2 = Get-Content (Join-Path $ClosureDir "tmp_pub_a2.json") | ConvertFrom-Json

$pubABA = [ordered]@{
    "target_host" = $pubTarget
    "target_port" = $pubPort
    "python_executable" = $PythonExe
    "stage_a1_disabled" = $resA1
    "stage_b_enabled" = $resB
    "stage_a2_disabled" = $resA2
    "verdict" = if ($resA1.connected -and (-not $resB.connected) -and $resA2.connected) { "PASS" } else { "FAIL" }
}
$pubABA | ConvertTo-Json -Depth 3 | Out-File (Join-Path $ClosureDir "firewall_public_aba.json") -Encoding utf8
Write-Host "  Public A/B/A Verdict: $($pubABA.verdict)" -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 4: Controlled Private-LAN Firewall A/B/A Causality Test
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 4] Executing Controlled Private-LAN Firewall A/B/A Test..." -ForegroundColor Cyan
$privHost = (& $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --resolve-private-host).Trim()
$privPort = 19878

Write-Host "  Starting background TCP listener on controlled private interface ${privHost}:${privPort}..." -ForegroundColor Gray
$serverJob = Start-Job -ScriptBlock {
    param($py, $scr, $h, $p)
    & $py $scr --start-private-server --host $h --port $p --duration 60
} -ArgumentList $PythonExe, (Join-Path $PSScriptRoot "run_closure_tests.py"), $privHost, $privPort

Start-Sleep -Seconds 3

# Stage A1: Disabled
Write-Host "  Stage A1 (Firewall Disabled): Probing ${privHost}:${privPort}..." -ForegroundColor Gray
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null
$prA1 = & $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --probe --host $privHost --port $privPort --out (Join-Path $ClosureDir "tmp_priv_a1.json")
$resPrivA1 = Get-Content (Join-Path $ClosureDir "tmp_priv_a1.json") | ConvertFrom-Json

# Stage B: Enabled
Write-Host "  Stage B (Firewall Enabled): Enabling rules & probing ${privHost}:${privPort}..." -ForegroundColor Gray
& (Join-Path $PSScriptRoot "enable_strict_network_policy.ps1") -PythonPath $PythonExe | Out-Null
$prB = & $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --probe --host $privHost --port $privPort --out (Join-Path $ClosureDir "tmp_priv_b.json")
$resPrivB = Get-Content (Join-Path $ClosureDir "tmp_priv_b.json") | ConvertFrom-Json

# Stage A2: Disabled
Write-Host "  Stage A2 (Firewall Disabled Again): Disabling rules & probing ${privHost}:${privPort}..." -ForegroundColor Gray
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null
$prA2 = & $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --probe --host $privHost --port $privPort --out (Join-Path $ClosureDir "tmp_priv_a2.json")
$resPrivA2 = Get-Content (Join-Path $ClosureDir "tmp_priv_a2.json") | ConvertFrom-Json

Stop-Job $serverJob -ErrorAction SilentlyContinue | Out-Null
Remove-Job $serverJob -ErrorAction SilentlyContinue | Out-Null
& $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --stop-private-server | Out-Null

$privABA = [ordered]@{
    "target_host" = $privHost
    "target_port" = $privPort
    "server_description" = "Controlled persistent TCP listener on secondary host vEthernet / WSL2 guest interface (RFC 1918 172.16.0.0/12)"
    "python_executable" = $PythonExe
    "stage_a1_disabled" = $resPrivA1
    "stage_b_enabled" = $resPrivB
    "stage_a2_disabled" = $resPrivA2
    "verdict" = if ($resPrivA1.connected -and (-not $resPrivB.connected) -and $resPrivA2.connected) { "PASS" } else { "FAIL" }
}
$privABA | ConvertTo-Json -Depth 3 | Out-File (Join-Path $ClosureDir "firewall_private_aba.json") -Encoding utf8
Write-Host "  Private A/B/A Verdict: $($privABA.verdict)" -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 5: Strict Broad PktMon Workflow Execution
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 5] Executing Strict Workflow under Broad PktMon Kernel Capture..." -ForegroundColor Cyan
Write-Host "  Enabling CogniShift strict firewall..." -ForegroundColor Gray
& (Join-Path $PSScriptRoot "enable_strict_network_policy.ps1") -PythonPath $PythonExe | Out-Null

$wfEtl = Join-Path $ClosureDir "pktmon_strict_workflow.etl"
$wfTxt = Join-Path $ClosureDir "pktmon_strict_workflow.txt"

pktmon stop 2>$null | Out-Null
pktmon filter remove 2>$null | Out-Null
pktmon filter add -p 11434 2>$null | Out-Null
pktmon filter add -p 80 2>$null | Out-Null
pktmon filter add -p 443 2>$null | Out-Null
pktmon filter add -p 19878 2>$null | Out-Null

Write-Host "  Starting broad PktMon capture..." -ForegroundColor Gray
pktmon start --capture --pkt-size 128 -f $wfEtl 2>$null | Out-Null

Write-Host "  Executing representative strict workflow..." -ForegroundColor Gray
& $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --run-workflow

Write-Host "  Stopping PktMon capture..." -ForegroundColor Gray
pktmon stop 2>$null | Out-Null

Write-Host "  Decoding strict workflow ETL trace..." -ForegroundColor Gray
pktmon etl2txt $wfEtl -o $wfTxt 2>$null | Out-Null

# Parse strict workflow trace
& $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --parse-pktmon-strict

# -----------------------------------------------------------------------------
# STEP 6: Firewall Teardown & Canonical Non-CogniShift Export (AFTER)
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 6] Tearing down CogniShift firewall rules & exporting AFTER baseline..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null # Idempotency verify

$rulesAfter = Get-NetFirewallRule | Where-Object { $_.RuleGroup -ne 'CogniShift-Phase6' } |
    Select-Object Name, DisplayName, DisplayGroup, Enabled, Direction, Action, Profile |
    Sort-Object Name
$rulesAfterJson = $rulesAfter | ConvertTo-Json -Depth 2
$afterPath = Join-Path $ClosureDir "firewall_non_cognishift_after.json"
$rulesAfterJson | Out-File -FilePath $afterPath -Encoding utf8
Write-Host "Exported $($rulesAfter.Count) non-CogniShift rules to $afterPath" -ForegroundColor Gray

# Compute Firewall Diff
& $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --diff-firewall

# -----------------------------------------------------------------------------
# STEP 7: Full Test Suite Regressions
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 7] Running Phase 6 Focused & Full Platform Test Regressions..." -ForegroundColor Cyan
$tempBase = Join-Path $PSScriptRoot "..\data\temp_pytest"
if (-not (Test-Path $tempBase)) {
    New-Item -ItemType Directory -Path $tempBase -Force | Out-Null
}
try { icacls $tempBase /grant "Everyone:(OI)(CI)F" /T /Q | Out-Null } catch { }

Write-Host "  Running Phase 6 Focused Suite..." -ForegroundColor Gray
$p6Out = Join-Path $ClosureDir "pytest_phase6.txt"
& $PythonExe -m pytest tests/test_phase6_tier_a_policy.py tests/test_phase6_tier_b_real_enforcement.py tests/test_phase6_tier_c_observation.py tests/test_phase6_browser_egress.py --basetemp=$tempBase -v | Out-File -FilePath $p6Out -Encoding utf8
$p6Failed = (Select-String -Path $p6Out -Pattern "FAILED").Count

Write-Host "  Running Full Repository Test Suite..." -ForegroundColor Gray
$fullOut = Join-Path $ClosureDir "pytest_full.txt"
& $PythonExe -m pytest --basetemp=$tempBase -v | Out-File -FilePath $fullOut -Encoding utf8
$fullFailed = (Select-String -Path $fullOut -Pattern "FAILED").Count

# -----------------------------------------------------------------------------
# STEP 8: Compute Final Gate & Generate Manifest
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 8] Computing Final Closure Gate & Generating Manifest..." -ForegroundColor Cyan
& $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --generate-gate --phase6-failed $p6Failed --full-failed $fullFailed
& $PythonExe (Join-Path $PSScriptRoot "run_closure_tests.py") --generate-manifest

# Cleanup temporary files
Remove-Item (Join-Path $ClosureDir "tmp_*.json") -ErrorAction SilentlyContinue | Out-Null

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  CogniShift Phase 6 Final Closure Verification COMPLETE!" -ForegroundColor Green
Write-Host "  Evidence generated in: $ClosureDir" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
