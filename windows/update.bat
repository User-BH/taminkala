@echo off
chcp 65001 >nul
net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
  exit /b
)
title Tamin Kala Bakhtar - update from GitHub
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\update.ps1"
echo.
pause
