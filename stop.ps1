# POUW Chain - 停止所有服务
# ===========================

Write-Host $env:SSH_PASSWORD
Write-Host "停止 POUW Chain 服务..." -ForegroundColor Yellow
Write-Host $env:SSH_PASSWORD

# 停止 Python 后端
$pythonProcs = Get-Process -Name python -ErrorAction SilentlyContinue
if ($pythonProcs) {
    Write-Host "  停止后端进程: $($pythonProcs.Count) 个" -ForegroundColor Cyan
    $pythonProcs | Stop-Process -Force -ErrorAction SilentlyContinue
}

# 停止 Node 前端
$nodeProcs = Get-Process -Name node -ErrorAction SilentlyContinue
if ($nodeProcs) {
    Write-Host "  停止前端进程: $($nodeProcs.Count) 个" -ForegroundColor Cyan
    $nodeProcs | Stop-Process -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 1

Write-Host $env:SSH_PASSWORD
Write-Host "所有服务已停止" -ForegroundColor Green
Write-Host $env:SSH_PASSWORD
