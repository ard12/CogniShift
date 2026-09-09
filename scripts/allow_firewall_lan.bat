@echo off
title CogniShift Windows Firewall Configuration
color 0E
echo ======================================================================
echo       CogniShift Firewall Configuration (LAN Ports 8443 and 8000)
echo ======================================================================
echo.
echo This requires Administrator privileges.
echo Rules are restricted to the local subnet on all Windows profiles.
echo.

net session >nul 2>&1
if errorlevel 1 (
    echo [INFO] Requesting Administrator permission...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    if errorlevel 1 (
        echo [ERROR] Administrator elevation was cancelled or unavailable.
        pause
        exit /b 1
    )
    exit /b 0
)

netsh advfirewall firewall delete rule name="CogniShift LAN Server (HTTPS 8443 Inbound)" >nul 2>&1
netsh advfirewall firewall add rule name="CogniShift LAN Server (HTTPS 8443 Inbound)" dir=in action=allow protocol=TCP localport=8443 remoteip=localsubnet profile=any >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] HTTPS 8443 allowed from the local subnet.
) else (
    echo [ERROR] Failed to configure HTTPS 8443.
)

netsh advfirewall firewall delete rule name="CogniShift LAN Server (HTTP 8000 Inbound)" >nul 2>&1
netsh advfirewall firewall add rule name="CogniShift LAN Server (HTTP 8000 Inbound)" dir=in action=allow protocol=TCP localport=8000 remoteip=localsubnet profile=any >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] HTTP 8000 allowed from the local subnet if explicitly enabled.
) else (
    echo [ERROR] Failed to configure HTTP 8000.
)

echo.
echo Firewall configuration complete.
pause
