$ErrorActionPreference = 'Continue'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $ScriptDir 'local-node.pid'

if (-not (Test-Path $PidFile)) {
    Write-Host '[Demo][Local] No local demo node PID file found.' -ForegroundColor Yellow
    exit 0
}

try {
    $nodePid = [int](Get-Content $PidFile)
    $proc = Get-Process -Id $nodePid -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id $nodePid -Force
        Write-Host "[Demo][Local] Stopped local node PID=$nodePid" -ForegroundColor Green
    } else {
        Write-Host '[Demo][Local] Process already stopped.' -ForegroundColor Yellow
    }
} catch {
    Write-Host '[Demo][Local] Failed to stop process from PID file.' -ForegroundColor Red
}

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
