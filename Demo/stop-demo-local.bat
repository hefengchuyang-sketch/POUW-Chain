@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%stop-demo-local.ps1"
if errorlevel 1 (
  echo [Demo][Local] stop failed.
  pause
)
endlocal
