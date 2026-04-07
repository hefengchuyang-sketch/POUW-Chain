@echo off
setlocal
title MainCoin Demo Launcher
echo ==========================================
echo MainCoin Demo - One Click Launcher
echo ==========================================
echo.
echo [Demo] Preparing startup...
set "SCRIPT_DIR=%~dp0"

if "%DEMO_FORCE_DOCKER%"=="1" (
  echo [Demo] Docker mode forced by DEMO_FORCE_DOCKER=1
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-demo.ps1"
) else (
  echo [Demo] Defaulting to LOCAL no-Docker mode.
  echo [Demo] To force Docker mode, set DEMO_FORCE_DOCKER=1 before running.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-demo-local.ps1"
)

set "EXIT_CODE=%ERRORLEVEL%"
echo.
if errorlevel 1 (
	echo [Demo] start-demo failed. Please review the error above.
	echo [Demo] Exit code: %EXIT_CODE%
	pause
)
if "%EXIT_CODE%"=="0" (
	echo [Demo] Demo finished. Press any key to close this window.
	pause
)
endlocal
