# CogniShift Sovereign Demo Reset CLI for Evaluators and Judges
# Usage:
#   .\scripts\reset_demo_for_judges.ps1                     # Resets Rohit to untrusted, preserves everyone else and alerts
#   .\scripts\reset_demo_for_judges.ps1 -DryRun             # Previews state without modifying database
#   .\scripts\reset_demo_for_judges.ps1 -Mode Complete      # Resets all client devices except host admin sitanshu
#   .\scripts\reset_demo_for_judges.ps1 -WipeMailbox        # Explicitly purges historical alerts

param(
    [ValidateSet("UntrustedOnly", "Complete")]
    [string]$Mode = "UntrustedOnly",

    [string]$TargetUser = "rohit",

    [switch]$WipeMailbox,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "         COGNISHIFT SOVEREIGN DEMO RESET FOR JUDGES & EVALUATORS         " -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Target Mode       : $Mode" -ForegroundColor Yellow
Write-Host "Target Untrusted  : $TargetUser" -ForegroundColor Yellow
Write-Host "Execution Type    : $(if ($DryRun) { 'DRY RUN (Inspection Only)' } else { 'APPLY (Active Reset)' })" -ForegroundColor $(if ($DryRun) { 'Magenta' } else { 'Green' })
Write-Host "Security Mailbox  : $(if ($WipeMailbox) { 'PURGE ALERTS' } else { 'PRESERVE HISTORICAL ALERTS (Default)' })" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------------------------" -ForegroundColor DarkGray

$scriptPath = Join-Path $PSScriptRoot "reset_team_demo_state.py"
$cmdArgs = @($scriptPath)

if (-not $DryRun) {
    $cmdArgs += "--apply"
}

if ($Mode -eq "Complete") {
    $cmdArgs += "--all-devices"
} else {
    $cmdArgs += "--untrusted-only"
}

$cmdArgs += "--target-user"
$cmdArgs += $TargetUser

if ($WipeMailbox) {
    $cmdArgs += "--wipe-mailbox"
} else {
    $cmdArgs += "--preserve-alerts"
}

python @cmdArgs

Write-Host "--------------------------------------------------------------------------" -ForegroundColor DarkGray
if (-not $DryRun) {
    Write-Host "[DEMO READY] System is now in verified pre-demonstration evaluation state." -ForegroundColor Green
    if ($Mode -eq "UntrustedOnly") {
        Write-Host "  1. Trusted operators (Aryan, Vicky, Zara, Rakshita) will log in smoothly." -ForegroundColor White
        Write-Host "  2. Untrusted user ($TargetUser) will be intercepted with 403 UNKNOWN_DEVICE." -ForegroundColor White
        Write-Host "  3. Admin (/security) will receive real-time security alert in SOC Mailbox." -ForegroundColor White
        Write-Host "  4. Admin approves device -> $TargetUser retries -> Access granted." -ForegroundColor White
    }
} else {
    Write-Host "[DRY RUN COMPLETE] To apply this reset, run without -DryRun." -ForegroundColor Magenta
}
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""
