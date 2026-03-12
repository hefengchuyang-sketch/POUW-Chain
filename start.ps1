# POUW Multi-Sector Chain - 一键启动脚本 (PowerShell)
# ================================================

param(
    [switch]$Mining,      # 启用挖矿
    [switch]$Provider,    # 作为算力提供者
    [switch]$FrontendOnly, # 仅启动前端
    [switch]$BackendOnly,  # 仅启动后端
    [switch]$Help         # 显示帮助
)

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "POUW Chain Launcher"

# 颜色函数
function Write-Color($text, $color = "White") {
    Write-Host $text -ForegroundColor $color
}

function Show-Banner {
    Write-Color @"

  ██████╗  ██████╗ ██╗   ██╗██╗    ██╗
  ██╔══██╗██╔═══██╗██║   ██║██║    ██║
  ██████╔╝██║   ██║██║   ██║██║ █╗ ██║
  ██╔═══╝ ██║   ██║██║   ██║██║███╗██║
  ██║     ╚██████╔╝╚██████╔╝╚███╔███╔╝
  ╚═╝      ╚═════╝  ╚═════╝  ╚══╝╚══╝
  
  Multi-Sector Chain - Proof of Useful Work
  Version 2.0.0
  
"@ "Cyan"
}

function Show-Help {
    Write-Color "用法: .\start.ps1 [选项]" "Yellow"
    Write-Host ''
    Write-Host "选项:"
    Write-Host "  -Mining        启用挖矿模式"
    Write-Host "  -Provider      作为算力提供者启动"
    Write-Host "  -FrontendOnly  仅启动前端"
    Write-Host "  -BackendOnly   仅启动后端"
    Write-Host "  -Help          显示此帮助"
    Write-Host ''
    Write-Host "示例:"
    Write-Host "  .\start.ps1                 # 普通用户模式（轻节点）"
    Write-Host "  .\start.ps1 -Mining         # 矿工模式"
    Write-Host "  .\start.ps1 -Provider       # 算力提供者模式"
    exit 0
}

if ($Help) { Show-Help }

Show-Banner

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# 检查 Python
Write-Color "[1/4] 检查 Python 环境..." "Yellow"
$pythonPath = $null
$possiblePaths = @(
    "$env:USERPROFILE\Anaconda3\python.exe",
    "$env:USERPROFILE\miniconda3\python.exe",
    "C:\Python311\python.exe",
    "C:\Python310\python.exe",
    "python"
)

foreach ($p in $possiblePaths) {
    try {
        $version = & $p --version 2>&1
        if ($version -match "Python 3") {
            $pythonPath = $p
            Write-Color "  找到 Python: $version" "Green"
            break
        }
    } catch {}
}

if (-not $pythonPath) {
    Write-Color "  错误: 未找到 Python 3，请先安装 Python" "Red"
    exit 1
}

# 检查 Node.js
Write-Color "[2/4] 检查 Node.js 环境..." "Yellow"
try {
    $nodeVersion = node --version 2>&1
    Write-Color "  找到 Node.js: $nodeVersion" "Green"
} catch {
    Write-Color "  错误: 未找到 Node.js，请先安装" "Red"
    exit 1
}

# 检查依赖
Write-Color "[3/4] 检查依赖..." "Yellow"
$missingDeps = @()
$deps = @("ecdsa", "mnemonic", "pycryptodome", "pyyaml", "colorama", "aiohttp")
foreach ($dep in $deps) {
    $check = & $pythonPath -c "import $($dep -replace '-','_' -replace 'pycryptodome','Crypto')" 2>&1
    if ($LASTEXITCODE -ne 0) {
        $missingDeps += $dep
    }
}

if ($missingDeps.Count -gt 0) {
    Write-Color "  安装缺失依赖: $($missingDeps -join ', ')" "Yellow"
    & $pythonPath -m pip install $missingDeps -q
}
Write-Color "  Python 依赖已就绪" "Green"

# 检查前端依赖
if (-not (Test-Path "frontend\node_modules")) {
    Write-Color "  安装前端依赖..." "Yellow"
    Push-Location frontend
    npm install --silent
    Pop-Location
}
Write-Color "  前端依赖已就绪" "Green"

# 停止旧的 POUW 进程（仅匹配 main.py，不影响其他 Python）
Write-Color "[4/4] 准备启动..." "Yellow"
Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    try { $_.CommandLine -match 'main\.py' } catch { $false }
} | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "vite" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# 构建启动参数
$backendArgs = "main.py"
$role = "light"

if ($Mining) {
    $backendArgs += " --mining"
    $role = "miner"
}
if ($Provider) {
    $backendArgs += " --role provider"
    $role = "provider"
}

# 启动服务
if (-not $FrontendOnly) {
    Write-Host ''
    Write-Color "启动后端服务 (角色: $role)..." "Cyan"
    $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList $backendArgs -WorkingDirectory $scriptPath -PassThru -WindowStyle Normal
    Write-Color "  后端 PID: $($backendProcess.Id)" "Green"
    Start-Sleep -Seconds 3
}

if (-not $BackendOnly) {
    Write-Color "启动前端服务..." "Cyan"
    Push-Location frontend
    $frontendProcess = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -PassThru -WindowStyle Normal
    Pop-Location
    Write-Color "  前端 PID: $($frontendProcess.Id)" "Green"
    Start-Sleep -Seconds 3
}

# 显示访问信息
Write-Host ''
Write-Color "========================================" "Green"
Write-Color "  POUW Chain 已启动!" "Green"
Write-Color "========================================" "Green"
Write-Host ''
if (-not $FrontendOnly) {
    Write-Color "  后端 RPC: http://127.0.0.1:8545" "White"
}
if (-not $BackendOnly) {
    Write-Color "  前端界面: http://localhost:3002" "White"
}
Write-Host ''
Write-Color "  角色: $role" "Yellow"
Write-Host ''
Write-Color "按任意键打开浏览器，按 Ctrl+C 退出..." "Gray"

try {
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    if (-not $BackendOnly) {
        Start-Process "http://localhost:3002"
    }
} catch {}

Write-Host ''
Write-Color "服务正在后台运行，关闭此窗口不会停止服务" "Yellow"
Write-Color "要停止服务，请运行: .\stop.ps1" "Yellow"
