# =============================================================================
# CogniShift Phase 6 - Final Evidence Reconciliation Master Verifier
# All-Port PktMon + Explicit Full Workflow + Pytest Count Reconciliation
# =============================================================================
# Requires elevated Administrator privileges for pktmon and netsh/firewall rules.
# =============================================================================
[CmdletBinding()]
param (
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CogniShift Phase 6 - Final Evidence Reconciliation" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# -----------------------------------------------------------------------------
# Check Elevation
# -----------------------------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] This script must be run as Administrator (elevated PowerShell)." -ForegroundColor Red
    Write-Host "Please re-open PowerShell as Administrator and execute:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\phase6_final_reconcile_verify.ps1" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Elevated Administrator session confirmed." -ForegroundColor Green

# -----------------------------------------------------------------------------
# Resolve Python
# -----------------------------------------------------------------------------
if (-not $PythonPath) {
    $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
} else {
    $PythonExe = $PythonPath
}

if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Python executable not found. Provide -PythonPath explicitly." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python Executable: $PythonExe" -ForegroundColor Green

$ReconcileDir = Join-Path $PSScriptRoot "..\artifacts\phase6_final_reconcile"
if (-not (Test-Path $ReconcileDir)) {
    New-Item -ItemType Directory -Path $ReconcileDir -Force | Out-Null
}

# -----------------------------------------------------------------------------
# STEP 1: Firewall Teardown & Export Baseline (BEFORE)
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 1] Tearing down any active CogniShift rules & exporting baseline (BEFORE)..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null

$rulesBefore = Get-NetFirewallRule | Where-Object { $_.RuleGroup -ne 'CogniShift-Phase6' } |
    Select-Object Name, DisplayName, DisplayGroup, Enabled, Direction, Action, Profile |
    Sort-Object Name
$rulesBeforeJson = $rulesBefore | ConvertTo-Json -Depth 2
$beforePath = Join-Path $ReconcileDir "firewall_non_cognishift_before.json"
$rulesBeforeJson | Out-File -FilePath $beforePath -Encoding utf8
Write-Host "Exported $($rulesBefore.Count) non-CogniShift rules to $beforePath" -ForegroundColor Gray

# -----------------------------------------------------------------------------
# STEP 2: All-Port PktMon Negative Control (Zero Port Whitelist)
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 2] Running All-Port PktMon Negative Control (No Port Filters)..." -ForegroundColor Cyan
$negEtl = Join-Path $ReconcileDir "pktmon_allport_negative_control.etl"
$negTxt = Join-Path $ReconcileDir "pktmon_allport_negative_control.txt"

pktmon stop 2>$null | Out-Null
pktmon filter remove 2>$null | Out-Null
Write-Host "  Starting all-port unfiltered PktMon capture..." -ForegroundColor Gray
pktmon start --capture --pkt-size 128 -f $negEtl 2>$null | Out-Null

Write-Host "  Generating negative control probes (loopback 11434, public 80, public 443)..." -ForegroundColor Gray
& $PythonExe (Join-Path $PSScriptRoot "run_final_reconciliation.py") --run-negative-control-probes

Write-Host "  Stopping all-port PktMon capture..." -ForegroundColor Gray
pktmon stop 2>$null | Out-Null

Write-Host "  Decoding negative control trace..." -ForegroundColor Gray
pktmon etl2txt $negEtl -o $negTxt 2>$null | Out-Null

Write-Host "  Parsing negative control trace..." -ForegroundColor Gray
& $PythonExe (Join-Path $PSScriptRoot "run_final_reconciliation.py") --parse-pktmon-allport-neg

# -----------------------------------------------------------------------------
# STEP 3: Strict Workflow Execution under All-Port PktMon Capture
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 3] Executing 7-Component Strict Workflow under All-Port PktMon..." -ForegroundColor Cyan
Write-Host "  Enabling CogniShift strict firewall..." -ForegroundColor Gray
& (Join-Path $PSScriptRoot "enable_strict_network_policy.ps1") -PythonPath $PythonExe | Out-Null

$wfEtl = Join-Path $ReconcileDir "pktmon_allport_strict_workflow.etl"
$wfTxt = Join-Path $ReconcileDir "pktmon_allport_strict_workflow.txt"

pktmon stop 2>$null | Out-Null
pktmon filter remove 2>$null | Out-Null
Write-Host "  Starting all-port unfiltered PktMon capture..." -ForegroundColor Gray
pktmon start --capture --pkt-size 128 -f $wfEtl 2>$null | Out-Null

Write-Host "  Executing 7 strict workflow components (Ollama, FastEmbed, RapidOCR, Moondream, Artifact, Docker, Forbidden Public Probe)..." -ForegroundColor Gray
& $PythonExe (Join-Path $PSScriptRoot "run_final_reconciliation.py") --run-strict-workflow-components

Write-Host "  Stopping all-port PktMon capture..." -ForegroundColor Gray
pktmon stop 2>$null | Out-Null

Write-Host "  Decoding strict workflow trace..." -ForegroundColor Gray
pktmon etl2txt $wfEtl -o $wfTxt 2>$null | Out-Null

Write-Host "  Parsing strict workflow trace & attributing traffic..." -ForegroundColor Gray
& $PythonExe (Join-Path $PSScriptRoot "run_final_reconciliation.py") --parse-pktmon-allport-strict

# -----------------------------------------------------------------------------
# STEP 4: Firewall Teardown & Baseline Preservation (AFTER)
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 4] Tearing down CogniShift firewall rules & exporting baseline (AFTER)..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null
& (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null

$rulesAfter = Get-NetFirewallRule | Where-Object { $_.RuleGroup -ne 'CogniShift-Phase6' } |
    Select-Object Name, DisplayName, DisplayGroup, Enabled, Direction, Action, Profile |
    Sort-Object Name
$rulesAfterJson = $rulesAfter | ConvertTo-Json -Depth 2
$afterPath = Join-Path $ReconcileDir "firewall_non_cognishift_after.json"
$rulesAfterJson | Out-File -FilePath $afterPath -Encoding utf8
Write-Host "Exported $($rulesAfter.Count) non-CogniShift rules to $afterPath" -ForegroundColor Gray

& $PythonExe (Join-Path $PSScriptRoot "run_final_reconciliation.py") --diff-firewall

# -----------------------------------------------------------------------------
# STEP 5: Pytest Collection Reconciliation & Inventory
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 5] Verifying Pytest Collection & Inventory..." -ForegroundColor Cyan
$colFile = Join-Path $ReconcileDir "pytest_collection.txt"
$fullFile = Join-Path $ReconcileDir "pytest_full.txt"
$invFile = Join-Path $ReconcileDir "pytest_inventory.json"

if (-not (Test-Path $colFile) -or -not (Test-Path $invFile)) {
    Write-Host "  Collecting test node IDs..." -ForegroundColor Gray
    & $PythonExe -m pytest --collect-only -q | Out-File -FilePath $colFile -Encoding utf8
}

# -----------------------------------------------------------------------------
# STEP 6: Compute Final Reconcile Gate & Manifest
# -----------------------------------------------------------------------------
Write-Host "`n[STEP 6] Computing Final Reconcile Gate & Manifest..." -ForegroundColor Cyan
& $PythonExe (Join-Path $PSScriptRoot "run_final_reconciliation.py") --generate-gate
& $PythonExe (Join-Path $PSScriptRoot "run_final_reconciliation.py") --generate-manifest

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  CogniShift Phase 6 Final Reconciliation Run COMPLETE!" -ForegroundColor Green
Write-Host "  Artifacts recorded in: $ReconcileDir" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
