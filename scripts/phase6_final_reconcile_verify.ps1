# =============================================================================
# CogniShift Phase 6 - Final Evidence Reconciliation Master Verifier
# All-Port PktMon + Explicit Full Workflow + Pytest Count Reconciliation
# =============================================================================
# Requires elevated Administrator privileges for pktmon and netsh/firewall rules.
# =============================================================================
[CmdletBinding()]
param (
    [string]$PythonPath = "",
    [switch]$SelfCheck = $false
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# -----------------------------------------------------------------------------
# State Tracking & Process Management for PktMon
# -----------------------------------------------------------------------------
$script:PktMonStartedByVerifier = $false
$script:StrictPolicyEnabled = $false
$script:PktMonMockCommand = $null

function Invoke-PktMonProcess {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Arguments
    )
    if ($script:PktMonMockCommand -ne $null) {
        return & $script:PktMonMockCommand $Arguments
    }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "pktmon.exe"
    $psi.Arguments = $Arguments
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $proc = [System.Diagnostics.Process]::Start($psi)
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()

    return [PSCustomObject]@{
        ExitCode = $proc.ExitCode
        StdOut   = $stdout.Trim()
        StdErr   = $stderr.Trim()
    }
}

function Stop-PktMonIfRunning {
    [CmdletBinding()]
    param(
        [switch]$AllowAlreadyStopped = $false
    )
    $res = Invoke-PktMonProcess -Arguments "stop"
    if ($res.ExitCode -eq 0) {
        return $true
    }
    $combined = "$($res.StdOut) $($res.StdErr)".Trim()
    if ($AllowAlreadyStopped -and ($combined -match "(?i)Packet Monitor is not running|not running")) {
        return $false
    }
    throw "PktMon stop failed (Exit $($res.ExitCode)): $combined"
}

function Remove-PktMonFilters {
    [CmdletBinding()]
    param()
    $res = Invoke-PktMonProcess -Arguments "filter remove"
    if ($res.ExitCode -eq 0) {
        return
    }
    $combined = "$($res.StdOut) $($res.StdErr)".Trim()
    if ($combined -match "(?i)no filters|not found|already removed") {
        return
    }
    throw "PktMon filter remove failed (Exit $($res.ExitCode)): $combined"
}

function Start-PktMonCapture {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$EtlPath
    )
    if ($script:PktMonStartedByVerifier) {
        throw "Internal error: PktMon capture is already marked as active by verifier."
    }
    # Clean prior running instances and any stale filters
    Stop-PktMonIfRunning -AllowAlreadyStopped | Out-Null
    Remove-PktMonFilters

    $res = Invoke-PktMonProcess -Arguments "start --capture --pkt-size 128 -f `"$EtlPath`""
    if ($res.ExitCode -ne 0) {
        $combined = "$($res.StdOut) $($res.StdErr)".Trim()
        throw "PktMon start failed (Exit $($res.ExitCode)): $combined"
    }
    $script:PktMonStartedByVerifier = $true
}

function Stop-PktMonCapture {
    [CmdletBinding()]
    param()
    if (-not $script:PktMonStartedByVerifier) {
        throw "Internal error: Stop-PktMonCapture called but verifier did not start an active capture."
    }
    # When stopping an active capture, AllowAlreadyStopped is strictly FALSE.
    # If the capture failed or died unexpectedly, this will throw!
    Stop-PktMonIfRunning -AllowAlreadyStopped:$false | Out-Null
    $script:PktMonStartedByVerifier = $false
}

function Convert-PktMonEtlToTxt {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$EtlPath,
        [Parameter(Mandatory=$true)]
        [string]$TxtPath
    )
    $res = Invoke-PktMonProcess -Arguments "etl2txt `"$EtlPath`" -o `"$TxtPath`""
    if ($res.ExitCode -ne 0) {
        $combined = "$($res.StdOut) $($res.StdErr)".Trim()
        throw "PktMon etl2txt failed (Exit $($res.ExitCode)): $combined"
    }
}

# -----------------------------------------------------------------------------
# Deterministic Unit Self-Check (Callable without elevation via -SelfCheck)
# -----------------------------------------------------------------------------
function Invoke-PktMonSelfCheck {
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  PktMon Helper Deterministic Unit Self-Check" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan

    $script:testsPassed = 0
    $script:totalTests = 0

    function Run-Assert {
        param(
            [string]$Name,
            [scriptblock]$Block
        )
        $script:totalTests++
        try {
            & $Block
            Write-Host "  [PASS] $Name" -ForegroundColor Green
            $script:testsPassed++
        } catch {
            Write-Host "  [FAIL] $Name - $_" -ForegroundColor Red
            throw
        }
    }

    # Reset state
    $script:PktMonStartedByVerifier = $false

    # Case A: Stop returns ExitCode 0 -> Accepted (returns true)
    Run-Assert "Case A: ExitCode 0 on stop is accepted as running and stopped" {
        $script:PktMonMockCommand = {
            param($arg)
            [PSCustomObject]@{ ExitCode = 0; StdOut = "PktMon stopped"; StdErr = "" }
        }
        $res = Stop-PktMonIfRunning -AllowAlreadyStopped:$false
        if ($res -ne $true) { throw "Expected `$true, got $res" }
    }

    # Case B: ExitCode != 0 with 'Packet Monitor is not running' and -AllowAlreadyStopped -> Accepted no-op (returns false)
    Run-Assert "Case B: ExitCode != 0 with 'not running' and AllowAlreadyStopped is clean no-op" {
        $script:PktMonMockCommand = {
            param($arg)
            [PSCustomObject]@{ ExitCode = 1; StdOut = ""; StdErr = "pktmon : Packet Monitor is not running." }
        }
        $res = Stop-PktMonIfRunning -AllowAlreadyStopped:$true
        if ($res -ne $false) { throw "Expected `$false, got $res" }
    }

    # Case C: ExitCode != 0 with 'Packet Monitor is not running' and NOT AllowAlreadyStopped -> Throws exception
    Run-Assert "Case C: ExitCode != 0 with 'not running' without AllowAlreadyStopped throws" {
        $script:PktMonMockCommand = {
            param($arg)
            [PSCustomObject]@{ ExitCode = 1; StdOut = ""; StdErr = "pktmon : Packet Monitor is not running." }
        }
        $threw = $false
        try {
            Stop-PktMonIfRunning -AllowAlreadyStopped:$false
        } catch {
            $threw = $true
            if ($_ -notmatch "Packet Monitor is not running") { throw "Unexpected error message: $_" }
        }
        if (-not $threw) { throw "Expected exception was not thrown" }
    }

    # Case D1: ExitCode != 0 with genuine error (e.g. Access is denied) with AllowAlreadyStopped -> Throws
    Run-Assert "Case D1: Genuine error (Access denied) with AllowAlreadyStopped throws" {
        $script:PktMonMockCommand = {
            param($arg)
            [PSCustomObject]@{ ExitCode = 5; StdOut = ""; StdErr = "Failed to communicate with the PktMon driver: Access is denied." }
        }
        $threw = $false
        try {
            Stop-PktMonIfRunning -AllowAlreadyStopped:$true
        } catch {
            $threw = $true
            if ($_ -notmatch "Access is denied") { throw "Unexpected error message: $_" }
        }
        if (-not $threw) { throw "Expected exception was not thrown" }
    }

    # Case D2: ExitCode != 0 with genuine error without AllowAlreadyStopped -> Throws
    Run-Assert "Case D2: Genuine error (Access denied) without AllowAlreadyStopped throws" {
        $script:PktMonMockCommand = {
            param($arg)
            [PSCustomObject]@{ ExitCode = 5; StdOut = ""; StdErr = "Failed to communicate with the PktMon driver: Access is denied." }
        }
        $threw = $false
        try {
            Stop-PktMonIfRunning -AllowAlreadyStopped:$false
        } catch {
            $threw = $true
            if ($_ -notmatch "Access is denied") { throw "Unexpected error message: $_" }
        }
        if (-not $threw) { throw "Expected exception was not thrown" }
    }

    # Case E: State Tracking - Start sets PktMonStartedByVerifier = $true and Stop resets to $false
    Run-Assert "Case E: State tracking across Start and Stop lifecycle" {
        $script:PktMonStartedByVerifier = $false
        $script:PktMonMockCommand = {
            param($arg)
            [PSCustomObject]@{ ExitCode = 0; StdOut = "OK"; StdErr = "" }
        }
        Start-PktMonCapture -EtlPath "mock.etl"
        if ($script:PktMonStartedByVerifier -ne $true) { throw "Expected PktMonStartedByVerifier to be `$true" }

        Stop-PktMonCapture
        if ($script:PktMonStartedByVerifier -ne $false) { throw "Expected PktMonStartedByVerifier to be `$false" }
    }

    # Case F: State Tracking - Active capture unexpectedly dying triggers failure
    Run-Assert "Case F: Active capture dying unexpectedly causes Stop-PktMonCapture to fail" {
        $script:PktMonStartedByVerifier = $false
        $script:PktMonMockCommand = {
            param($arg)
            if ($arg -match "^start") {
                return [PSCustomObject]@{ ExitCode = 0; StdOut = "Started"; StdErr = "" }
            }
            if ($arg -match "^stop") {
                return [PSCustomObject]@{ ExitCode = 1; StdOut = ""; StdErr = "Packet Monitor is not running." }
            }
            return [PSCustomObject]@{ ExitCode = 0; StdOut = ""; StdErr = "" }
        }
        Start-PktMonCapture -EtlPath "mock.etl"
        $threw = $false
        try {
            Stop-PktMonCapture
        } catch {
            $threw = $true
            if ($_ -notmatch "Packet Monitor is not running") { throw "Unexpected error message: $_" }
        }
        if (-not $threw) { throw "Expected Stop-PktMonCapture to throw when active capture died" }
    }

    # Case G: Stop-PktMonCapture when not marked active throws internal error
    Run-Assert "Case G: Stop-PktMonCapture throws when not active" {
        $script:PktMonStartedByVerifier = $false
        $threw = $false
        try {
            Stop-PktMonCapture
        } catch {
            $threw = $true
            if ($_ -notmatch "verifier did not start an active capture") { throw "Unexpected error message: $_" }
        }
        if (-not $threw) { throw "Expected Stop-PktMonCapture to throw" }
    }

    # Case H: Start-PktMonCapture when already active throws internal error
    Run-Assert "Case H: Start-PktMonCapture throws when already active" {
        $script:PktMonStartedByVerifier = $true
        $threw = $false
        try {
            Start-PktMonCapture -EtlPath "mock.etl"
        } catch {
            $threw = $true
            if ($_ -notmatch "already marked as active") { throw "Unexpected error message: $_" }
        }
        if (-not $threw) { throw "Expected Start-PktMonCapture to throw" }
    }

    # Reset mock command & state
    $script:PktMonMockCommand = $null
    $script:PktMonStartedByVerifier = $false

    Write-Host "`nAll $script:totalTests PktMon helper unit checks PASSED ($script:testsPassed/$script:totalTests)." -ForegroundColor Green
}

if ($SelfCheck) {
    Invoke-PktMonSelfCheck
    exit 0
}

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

try {
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

    Write-Host "  Starting all-port unfiltered PktMon capture..." -ForegroundColor Gray
    Start-PktMonCapture -EtlPath $negEtl

    Write-Host "  Generating negative control probes (loopback 11434, public 80, public 443)..." -ForegroundColor Gray
    & $PythonExe (Join-Path $PSScriptRoot "run_final_reconciliation.py") --run-negative-control-probes

    Write-Host "  Stopping all-port PktMon capture..." -ForegroundColor Gray
    Stop-PktMonCapture

    Write-Host "  Decoding negative control trace..." -ForegroundColor Gray
    Convert-PktMonEtlToTxt -EtlPath $negEtl -TxtPath $negTxt

    Write-Host "  Parsing negative control trace..." -ForegroundColor Gray
    & $PythonExe (Join-Path $PSScriptRoot "run_final_reconciliation.py") --parse-pktmon-allport-neg

    # -----------------------------------------------------------------------------
    # STEP 3: Strict Workflow Execution under All-Port PktMon Capture
    # -----------------------------------------------------------------------------
    Write-Host "`n[STEP 3] Executing 7-Component Strict Workflow under All-Port PktMon..." -ForegroundColor Cyan
    Write-Host "  Enabling CogniShift strict firewall..." -ForegroundColor Gray
    & (Join-Path $PSScriptRoot "enable_strict_network_policy.ps1") -PythonPath $PythonExe | Out-Null
    $script:StrictPolicyEnabled = $true

    $wfEtl = Join-Path $ReconcileDir "pktmon_allport_strict_workflow.etl"
    $wfTxt = Join-Path $ReconcileDir "pktmon_allport_strict_workflow.txt"

    Write-Host "  Starting all-port unfiltered PktMon capture..." -ForegroundColor Gray
    Start-PktMonCapture -EtlPath $wfEtl

    Write-Host "  Executing 7 strict workflow components (Ollama, FastEmbed, RapidOCR, Moondream, Artifact, Docker, Forbidden Public Probe)..." -ForegroundColor Gray
    & $PythonExe (Join-Path $PSScriptRoot "run_final_reconciliation.py") --run-strict-workflow-components

    Write-Host "  Stopping all-port PktMon capture..." -ForegroundColor Gray
    Stop-PktMonCapture

    Write-Host "  Decoding strict workflow trace..." -ForegroundColor Gray
    Convert-PktMonEtlToTxt -EtlPath $wfEtl -TxtPath $wfTxt

    Write-Host "  Parsing strict workflow trace & attributing traffic..." -ForegroundColor Gray
    & $PythonExe (Join-Path $PSScriptRoot "run_final_reconciliation.py") --parse-pktmon-allport-strict

    # -----------------------------------------------------------------------------
    # STEP 4: Firewall Teardown & Baseline Preservation (AFTER)
    # -----------------------------------------------------------------------------
    Write-Host "`n[STEP 4] Tearing down CogniShift firewall rules & exporting baseline (AFTER)..." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null
    & (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null
    $script:StrictPolicyEnabled = $false

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
} finally {
    if ($script:PktMonStartedByVerifier) {
        Write-Host "Cleaning up active PktMon capture in finally block..." -ForegroundColor Yellow
        try {
            Stop-PktMonCapture
        } catch {
            Write-Warning "Failed to stop active PktMon capture in finally: $_"
        }
    } else {
        try {
            Stop-PktMonIfRunning -AllowAlreadyStopped | Out-Null
        } catch { }
    }
    if ($script:StrictPolicyEnabled) {
        Write-Host "Tearing down strict network policy in finally block..." -ForegroundColor Yellow
        try {
            & (Join-Path $PSScriptRoot "disable_strict_network_policy.ps1") | Out-Null
            $script:StrictPolicyEnabled = $false
        } catch { }
    }
}
