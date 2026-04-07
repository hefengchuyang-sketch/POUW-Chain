@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%stop-demo.ps1"
if errorlevel 1 (
	echo.
	echo [Demo] stop-demo failed. Please review the error above.
	pause
)
endlocal
