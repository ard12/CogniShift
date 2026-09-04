# CogniShift Phase 6: Human Operator Independent Verification Guide

This document contains the step-by-step commands to independently verify Windows Defender Firewall enforcement and OS-level network observation in an elevated Administrator session.

---

## Prerequisites
1. Open PowerShell as Administrator (Right click PowerShell -> **Run as Administrator**).
2. Navigate to the CogniShift directory:
   ```powershell
   cd C:\Users\sitan\OneDrive\Desktop\CogniShift
   ```

---

## Option A: Automated Script (Recommended)
Run the all-in-one verification script:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\phase6_manual_verify.ps1
```
This script runs all steps below, writes machine-readable evidence files to `artifacts/phase6_firewall_final/`, and cleanly restores the firewall upon completion.

---

## Option B: Step-by-Step Manual Commands

### 1. Verify Target Python Runtime
```powershell
python -c "import sys; print(sys.executable)"
```
*Expected:* `C:\Users\sitan\AppData\Local\Programs\Python\Python312\python.exe`

### 2. Enable Strict Windows Defender Firewall Rules
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\enable_strict_network_policy.ps1
```
*Expected:* Reports rules created under group `CogniShift-Phase6`.

### 3. Inspect Active CogniShift Rules
```powershell
Get-NetFirewallRule -Group "CogniShift-Phase6" | Format-Table DisplayName, Enabled, Direction, Action, Profile
```
*Expected:*
- `CogniShift-Phase6-Allow-Loopback-Out`: Allow, Outbound
- `CogniShift-Phase6-Allow-Loopback-In`: Allow, Inbound (Port 8000)
- `CogniShift-Phase6-Block-Outbound-WAN`: Block, Outbound

### 4. Direct Loopback Socket Test (Bypasses Application NetworkPolicy)
```powershell
python scripts/test_os_firewall_sockets.py --target-host 127.0.0.1 --target-port 11434 --output-json artifacts/phase6_firewall_final/firewall_loopback_test.json
```
*Expected:* `Connected=True, Error=None`

### 5. Direct Public Socket Test (Bypasses Application NetworkPolicy)
```powershell
python scripts/test_os_firewall_sockets.py --target-host 1.1.1.1 --target-port 80 --output-json artifacts/phase6_firewall_final/firewall_public_test.json
```
*Expected:* `Connected=False, Error=PermissionError (WinError 10013)` or `TimeoutError` (blocked by Windows Firewall).

### 6. Direct Unauthorized Private LAN Socket Test
```powershell
python scripts/test_os_firewall_sockets.py --target-host 192.168.1.254 --target-port 80 --output-json artifacts/phase6_firewall_final/firewall_private_test.json
```
*Expected:* `Connected=False` (blocked by Windows Firewall).

### 7. Disable Firewall Rules
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\disable_strict_network_policy.ps1
```
*Expected:* Rules cleanly removed.

### 8. Public Control Test (Proving Firewall Causality)
With firewall disabled, repeat the public connection:
```powershell
python scripts/test_os_firewall_sockets.py --target-host 1.1.1.1 --target-port 80 --output-json artifacts/phase6_firewall_final/firewall_public_control_test.json
```
*Expected:* `Connected=True, Error=None` (Proves failure in Step 5 was caused by the OS firewall, not general network loss).

### 9. Independent OS Packet Observer (PktMon)
```powershell
pktmon filter remove
pktmon filter add -p 11434
pktmon start --capture --pkt-size 128 -f artifacts/phase6_firewall_final/os_trace.etl
python scripts/test_os_firewall_sockets.py --target-host 127.0.0.1 --target-port 11434 --output-json artifacts/phase6_firewall_final/os_observer_negative_control.json
pktmon stop
pktmon etl2txt artifacts/phase6_firewall_final/os_trace.etl -o artifacts/phase6_firewall_final/os_trace.txt
Get-Content artifacts/phase6_firewall_final/os_trace.txt | Select-Object -First 20
```

### 10. Verify Full Test Suite
```powershell
python -m pytest -v
```
*Expected:* `196 passed`
