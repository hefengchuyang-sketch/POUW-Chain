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

echo [1/3] 检查环境...

REM 查找 Python
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
        echo   [错误] 未找到 Python，请先安装
        pause
        exit /b 1
    )
)

echo   Python: %PYTHON_PATH%

REM 检查 Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo   [错误] 未找到 Node.js，请先安装
    pause
    exit /b 1
)
echo   Node.js: 已安装

echo.
echo [2/3] 启动后端服务...
start "POUW Backend" cmd /k "%PYTHON_PATH% main.py"
timeout /t 3 /nobreak >nul

echo [3/3] 启动前端服务...
cd frontend
start "POUW Frontend" cmd /k "npm run dev"
cd ..

timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo   POUW Chain 已启动!
echo ========================================
echo.
echo   后端 RPC: http://127.0.0.1:8545
echo   前端界面: http://localhost:3002
echo.
echo   按任意键打开浏览器...
pause >nul

start http://localhost:3002

echo.
echo 服务正在后台运行
echo 关闭对应的命令行窗口可停止服务
echo.
pause
