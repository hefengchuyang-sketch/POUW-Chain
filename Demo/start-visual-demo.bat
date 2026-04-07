@echo off
setlocal
title MainCoin Visual Demo Launcher
echo ==========================================
echo MainCoin - Visual Demo (Frontend)
echo ==========================================
echo.
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-visual-demo.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if errorlevel 1 (
  echo [VisualDemo] Launch failed. Exit code: %EXIT_CODE%
  pause
)
if "%EXIT_CODE%"=="0" (
  echo [VisualDemo] Browser opened. Press any key to close this window.
  pause
)
endlocal
