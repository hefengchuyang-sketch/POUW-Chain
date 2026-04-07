@echo off
chcp 65001 >nul
title POUW Chain Launcher

echo.
echo   ██████╗  ██████╗ ██╗   ██╗██╗    ██╗
echo   ██╔══██╗██╔═══██╗██║   ██║██║    ██║
echo   ██████╔╝██║   ██║██║   ██║██║ █╗ ██║
echo   ██╔═══╝ ██║   ██║██║   ██║██║███╗██║
echo   ██║     ╚██████╔╝╚██████╔╝╚███╔███╔╝
echo   ╚═╝      ╚═════╝  ╚═════╝  ╚══╝╚══╝
echo.
echo   Multi-Sector Chain - Proof of Useful Work
echo   Version 2.0.0
echo.

cd /d "%~dp0"

echo [1/3] Checking environment...

REM Find Python
set PYTHON_PATH=
if exist "%USERPROFILE%\Anaconda3\python.exe" (
    set PYTHON_PATH=%USERPROFILE%\Anaconda3\python.exe
) else if exist "%USERPROFILE%\miniconda3\python.exe" (
    set PYTHON_PATH=%USERPROFILE%\miniconda3\python.exe
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PYTHON_PATH=python
    ) else (
        echo   [ERROR] Python not found. Please install it first.
        pause
        exit /b 1
    )
)

echo   Python: %PYTHON_PATH%

REM Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] Node.js not found. Please install it first.
    pause
    exit /b 1
)
echo   Node.js: installed

echo.
echo [2/3] Starting backend service...
start "POUW Backend" cmd /k "%PYTHON_PATH% main.py"
timeout /t 3 /nobreak >nul

echo [3/3] Starting frontend service...
cd frontend
start "POUW Frontend" cmd /k "npm run dev"
cd ..

timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo   POUW Chain started!
echo ========================================
echo.
echo   Backend RPC: http://127.0.0.1:8545
echo   Frontend UI: http://localhost:3002
echo.
echo   Press any key to open browser...
pause >nul

start http://localhost:3002

echo.
echo Services are running in background terminals
echo Close the corresponding terminal windows to stop services
echo.
pause
