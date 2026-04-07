$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$PidFile = Join-Path $ScriptDir 'local-node.pid'
$NodeLog = Join-Path $ScriptDir 'local-node.log'
$NodeErr = Join-Path $ScriptDir 'local-node.err.log'

Set-Location $RepoRoot

# Avoid Windows GBK console encoding crashes from emoji/unicode logs.
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

Write-Host '[Demo][Local] Starting local node without Docker...' -ForegroundColor Cyan

if (Test-Path $PidFile) {
    try {
        $oldPid = [int](Get-Content $PidFile -ErrorAction Stop)
        $oldProc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($oldProc) {
            Write-Host "[Demo][Local] Existing node process found (PID=$oldPid), reusing..." -ForegroundColor Yellow
        } else {
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path $PidFile)) {
    $proc = Start-Process -FilePath "py" -ArgumentList @(
        "-3",
        "main.py",
        "--config", "config.yaml",
        "--rpc-port", "18545",
        "--port", "19333",
        "--data-dir", "data"
    ) -WorkingDirectory $RepoRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $NodeLog -RedirectStandardError $NodeErr

    Set-Content -Path $PidFile -Value $proc.Id
    Write-Host "[Demo][Local] Node started (PID=$($proc.Id))." -ForegroundColor Green
}

$env:DEMO_RPC_URL = 'https://127.0.0.1:18545'
Write-Host '[Demo][Local] Running end-to-end demo...' -ForegroundColor Cyan
py -3 "$ScriptDir/demo_runner.py"

if ($LASTEXITCODE -eq 0) {
    Write-Host '[Demo][Local] Demo finished successfully.' -ForegroundColor Green
} else {
    Write-Host '[Demo][Local] Demo failed. Check logs:' -ForegroundColor Red
    Write-Host "  $NodeLog"
    Write-Host "  $NodeErr"
    exit $LASTEXITCODE
}
