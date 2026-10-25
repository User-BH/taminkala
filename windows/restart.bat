@echo off
chcp 65001 >nul
net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
  exit /b
)
title Tamin Kala Bakhtar - restart
schtasks /End /TN TaminKala >nul 2>&1
timeout /t 2 /nobreak >nul
schtasks /Run /TN TaminKala
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\status.ps1"
echo.
pause
