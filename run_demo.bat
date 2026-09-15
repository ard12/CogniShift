@echo off
title CogniShift Sovereign Edge Server (SIH Finals)
color 0B
echo ======================================================================
echo           COGNISHIFT SOVEREIGN ON-PREMISE AI WORKBENCH
echo              Smart India Hackathon Finals (SIH26117)
echo ======================================================================
echo.
cd /d "%~dp0"

echo [1/3] Verifying Python and Virtual Environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in system PATH.
    pause
    exit /b 1
)

echo [2/3] Checking Ollama Local Inference Service...
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Ollama does not appear to be running on http://127.0.0.1:11434.
    echo Please make sure 'ollama serve' is running in a separate window.
    echo.
) else (
    echo [OK] Ollama local service is reachable.
)

echo [3/3] Launching CogniShift LAN Secure Server on Port 8443...
echo The launcher will print the current hotspot IP. Always include https://.
echo For a single-laptop no-certificate fallback, use run_demo_http.bat.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start_lan_demo.ps1" -RestartExisting

pause
