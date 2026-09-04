# =============================================================================
# CogniShift Phase 6 - PktMon Helper Unit Self-Check Runner
# =============================================================================
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$VerifierScript = Join-Path $PSScriptRoot "phase6_final_reconcile_verify.ps1"
if (-not (Test-Path $VerifierScript)) {
    throw "Target script not found: $VerifierScript"
}

Write-Host "Invoking PktMon Helper Self-Check via $VerifierScript -SelfCheck ..." -ForegroundColor Cyan
& $VerifierScript -SelfCheck
