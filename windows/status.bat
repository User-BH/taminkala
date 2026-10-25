@echo off
chcp 65001 >nul
title Tamin Kala Bakhtar - status
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\status.ps1"
echo.
pause
