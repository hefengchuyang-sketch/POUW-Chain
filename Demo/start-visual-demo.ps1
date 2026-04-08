$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$PidFile = Join-Path $ScriptDir 'local-node.pid'
$NodeLog = Join-Path $ScriptDir 'local-node.log'
$NodeErr = Join-Path $ScriptDir 'local-node.err.log'
$DemoUrl = 'https://127.0.0.1:18545/demo'

Set-Location $RepoRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

Write-Host '[VisualDemo] Building frontend (frontend/dist)...' -ForegroundColor Cyan
Push-Location (Join-Path $RepoRoot 'frontend')
try {
    if (-not (Test-Path 'node_modules')) {
        Write-Host '[VisualDemo] Installing frontend dependencies...' -ForegroundColor Yellow
        npm install
        if ($LASTEXITCODE -ne 0) {
            throw 'npm install failed'
        }
    }

    npm run build
    if ($LASTEXITCODE -ne 0) {
        throw 'npm run build failed'
    }
} finally {
    Pop-Location
}

Write-Host '[VisualDemo] Starting local node...' -ForegroundColor Cyan

if (Test-Path $PidFile) {
    try {
        $oldPid = [int](Get-Content $PidFile -ErrorAction Stop)
        $oldProc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($oldProc) {
            Write-Host "[VisualDemo] Reusing node process PID=$oldPid" -ForegroundColor Yellow
        } else {
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path $PidFile)) {
    $proc = Start-Process -FilePath 'py' -ArgumentList @(
        '-3',
        'main.py',
        '--config', 'config.yaml',
        '--rpc-port', '18545',
        '--port', '19333',
        '--data-dir', 'data'
    ) -WorkingDirectory $RepoRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $NodeLog -RedirectStandardError $NodeErr

    Set-Content -Path $PidFile -Value $proc.Id
    Write-Host "[VisualDemo] Node started PID=$($proc.Id)" -ForegroundColor Green
}

[System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }

Write-Host '[VisualDemo] Waiting for /rpc ready...' -ForegroundColor Cyan
$ready = $false
$probeCode = @"
import json
import ssl
import sys
import urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

payload = json.dumps({
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'blockchain_getHeight',
    'params': {}
}).encode('utf-8')

req = urllib.request.Request(
    'https://127.0.0.1:18545/rpc',
    data=payload,
    headers={'Content-Type': 'application/json'},
)

try:
    with urllib.request.urlopen(req, timeout=3, context=ctx) as resp:
        body = json.loads(resp.read().decode('utf-8'))
    sys.exit(0 if 'result' in body else 1)
except Exception:
    sys.exit(1)
"@

for ($i = 0; $i -lt 40; $i++) {
    py -3 -c $probeCode | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $ready) {
    Write-Host '[VisualDemo] Node not ready. Check logs:' -ForegroundColor Red
    Write-Host "  $NodeLog"
    Write-Host "  $NodeErr"
    exit 1
}

Write-Host '[VisualDemo] Opening browser...' -ForegroundColor Green
Start-Process $DemoUrl
Write-Host '[VisualDemo] Opened: https://127.0.0.1:18545/demo' -ForegroundColor Green
Write-Host '[VisualDemo] In page, click "Run Visual Demo" to run full visible flow.' -ForegroundColor Yellow
