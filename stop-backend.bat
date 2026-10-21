@echo off
REM ?????????? Flask ??
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-backend.ps1"
pause
