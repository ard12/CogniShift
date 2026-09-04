<#
.SYNOPSIS
    Disables CogniShift Phase 6 Strict Network Policy via Windows Defender Firewall.
.DESCRIPTION
    Removes all firewall rules under group 'CogniShift-Phase6', restoring default
    networking for the target Python process.
    Requires Administrator privileges.
#>
[CmdletBinding()]
param()

# 1. Administrator Privilege Check
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Administrator privileges required. Please run PowerShell as Administrator to modify Windows Defender Firewall."
    exit 1
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CogniShift Phase 6 - Disable Strict Network Policy" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$existingRules = Get-NetFirewallRule -Group "CogniShift-Phase6" -ErrorAction SilentlyContinue

if ($existingRules) {
    $count = ($existingRules | Measure-Object).Count
    Write-Host "Removing $count CogniShift-Phase6 firewall rule(s)..." -ForegroundColor Yellow
    Remove-NetFirewallRule -Group "CogniShift-Phase6" -ErrorAction SilentlyContinue
    Write-Host "SUCCESS: Removed all CogniShift-Phase6 firewall rules." -ForegroundColor Green
} else {
    Write-Host "No active CogniShift-Phase6 firewall rules found." -ForegroundColor Gray
}

Write-Host "============================================================" -ForegroundColor Cyan
