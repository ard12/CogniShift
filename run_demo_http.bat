@echo off
title CogniShift Local Server (HTTP Port 8000 - Loopback Fallback)
color 0A
echo ======================================================================
echo           COGNISHIFT SOVEREIGN ON-PREMISE AI WORKBENCH
echo        Zero-Certificate HTTP Mode (This Laptop Only, Port 8000)
echo ======================================================================
echo.
cd /d "%~dp0"

echo [1/3] Verifying Python Environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in system PATH.
    pause
    exit /b 1
)

echo [2/3] Checking Ollama Local Inference Service...
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Ollama is not running on http://127.0.0.1:11434.
    echo Start "ollama serve" before model-backed demonstrations.
) else (
    echo [OK] Ollama local service is reachable.
)

echo [3/3] Launching the loopback HTTP fallback on Port 8000...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start_http_demo.ps1" -RestartExisting

pause
