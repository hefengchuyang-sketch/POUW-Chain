# POUW Chain - 3 节点 Docker 测试脚本
# 用法: .\scripts\test_3node.ps1

param(
    [switch]$Build,
    [switch]$Down,
    [switch]$Logs,
    [int]$WaitSeconds = 30
)

$ErrorActionPreference = "Continue"

# 颜色输出
function Write-Step($msg) { Write-Host "`n[STEP] $msg" -ForegroundColor Cyan }
function Write-OK($msg) { Write-Host "[  OK] $msg" -ForegroundColor Green }
function Write-FAIL($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }
function Write-INFO($msg) { Write-Host "[INFO] $msg" -ForegroundColor Yellow }

# ------- 停止 -------
if ($Down) {
    Write-Step "停止所有容器..."
    docker-compose down -v
    Write-OK "已停止"
    exit 0
}

# ------- 日志 -------
if ($Logs) {
    docker-compose logs -f --tail=50
    exit 0
}

Write-Host "========================================" -ForegroundColor Magenta
Write-Host "   POUW Chain - 3 节点集成测试" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta

# Step 1: 构建镜像
Write-Step "1/6 构建 Docker 镜像..."
if ($Build -or -not (docker images pouw-chain -q 2>$null)) {
    docker-compose build --no-cache
    if ($LASTEXITCODE -ne 0) { Write-FAIL "构建失败"; exit 1 }
}
Write-OK "镜像就绪"

# Step 2: 启动 3 个节点 (bootstrap + node1 + miner)
Write-Step "2/6 启动 bootstrap + node1 + miner..."
docker-compose down -v 2>$null
docker-compose up -d bootstrap node1 miner
if ($LASTEXITCODE -ne 0) { Write-FAIL "启动失败"; exit 1 }
Write-OK "3 个容器已启动"

# Step 3: 等待节点就绪
Write-Step "3/6 等待节点启动 ($WaitSeconds 秒)..."
Start-Sleep -Seconds $WaitSeconds
Write-OK "等待完成"

# Step 4: 健康检查 - RPC 连通性
Write-Step "4/6 RPC 连通性检查..."
$nodes = @(
    @{ Name = "bootstrap"; Port = 8545 },
    @{ Name = "node1";     Port = 8546 },
    @{ Name = "miner";     Port = 8548 }
)

$allHealthy = $true
foreach ($node in $nodes) {
    try {
        $body = '{"jsonrpc":"2.0","method":"node_getStatus","params":[],"id":1}'
        $resp = Invoke-RestMethod -Uri "http://localhost:$($node.Port)" `
            -Method POST -Body $body -ContentType "application/json" -TimeoutSec 5
        if ($resp.result) {
            Write-OK "$($node.Name) (port $($node.Port)) - 在线"
        } else {
            Write-FAIL "$($node.Name) - RPC 无响应"
            $allHealthy = $false
        }
    } catch {
        Write-FAIL "$($node.Name) (port $($node.Port)) - 连接失败: $_"
        $allHealthy = $false
    }
}

if (-not $allHealthy) {
    Write-INFO "部分节点未就绪，查看日志: docker-compose logs"
}

# Step 5: 链高度检查
Write-Step "5/6 链高度与共识检查..."
$heights = @()
foreach ($node in $nodes) {
    try {
        $body = '{"jsonrpc":"2.0","method":"chain_getInfo","params":[],"id":1}'
        $resp = Invoke-RestMethod -Uri "http://localhost:$($node.Port)" `
            -Method POST -Body $body -ContentType "application/json" -TimeoutSec 5
        $h = $resp.result.height
        $heights += $h
        Write-INFO "$($node.Name): 高度 #$h"
    } catch {
        Write-FAIL "$($node.Name) chain_getInfo 失败"
        $heights += -1
    }
}

$minerHeight = $heights[2]
if ($minerHeight -gt 0) {
    Write-OK "矿工正在出块 (高度 #$minerHeight)"
} else {
    Write-INFO "矿工尚未出块 (可能需要更多时间)"
}

# Step 6: P2P 连接检查
Write-Step "6/6 P2P 对等节点检查..."
foreach ($node in $nodes) {
    try {
        $body = '{"jsonrpc":"2.0","method":"p2p_getInfo","params":[],"id":1}'
        $resp = Invoke-RestMethod -Uri "http://localhost:$($node.Port)" `
            -Method POST -Body $body -ContentType "application/json" -TimeoutSec 5
        $peers = $resp.result.connected_peers
        if ($peers -gt 0) {
            Write-OK "$($node.Name): $peers 个对等节点"
        } else {
            Write-INFO "$($node.Name): 尚无连接的对等节点"
        }
    } catch {
        Write-FAIL "$($node.Name) p2p_getInfo 失败"
    }
}

Write-Host "`n========================================" -ForegroundColor Magenta
Write-Host "   测试完成" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host $env:SSH_PASSWORD
Write-Host "后续操作:" -ForegroundColor Yellow
Write-Host "  查看日志:  .\scripts\test_3node.ps1 -Logs"
Write-Host "  停止集群:  .\scripts\test_3node.ps1 -Down"
Write-Host "  重新测试:  .\scripts\test_3node.ps1 -Build"
Write-Host $env:SSH_PASSWORD
