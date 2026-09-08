@echo off
title CogniShift Route Preflight Check
color 0A
echo ======================================================================
echo           COGNISHIFT PREFLIGHT ROUTE VERIFICATION
echo ======================================================================
echo.
cd /d "%~dp0"
python scripts\preflight_routes.py
echo.
pause
