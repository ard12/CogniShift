@echo off
title CogniShift Reset Demo For Judges
color 0E
echo ======================================================================
echo           COGNISHIFT DEMO RESET FOR JUDGES & EVALUATORS
echo ======================================================================
echo.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\reset_demo_for_judges.ps1"
echo.
pause
