@echo off
setlocal
title MainCoin Demo Launcher (Local No-Docker)
echo ==========================================
echo MainCoin Demo - Local Mode (No Docker)
echo ==========================================
echo.
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-demo-local.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if errorlevel 1 (
  echo [Demo][Local] failed. Please review the error above.
  echo [Demo][Local] Exit code: %EXIT_CODE%
  pause
)
if "%EXIT_CODE%"=="0" (
  echo [Demo][Local] Demo finished. Press any key to close this window.
  pause
)
endlocal
