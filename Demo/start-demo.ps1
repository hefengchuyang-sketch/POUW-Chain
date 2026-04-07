$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
Set-Location $RepoRoot

Write-Host '[Demo] Script path: ' $ScriptDir -ForegroundColor DarkGray
Write-Host '[Demo] Working directory: ' $RepoRoot -ForegroundColor DarkGray
Write-Host '[Demo] Checking Docker status...' -ForegroundColor Cyan

cmd /c "docker info >nul 2>nul"
if ($LASTEXITCODE -ne 0) {
    $dockerDesktopExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerDesktopExe) {
        Write-Host '[Demo] Docker Desktop is not running. Attempting to start it...' -ForegroundColor Yellow
        Start-Process -FilePath $dockerDesktopExe | Out-Null
        Write-Host '[Demo] Waiting for Docker Desktop to become ready (up to 120s)...' -ForegroundColor Yellow

        $ready = $false
        for ($i = 0; $i -lt 60; $i++) {
            Start-Sleep -Seconds 2
            if (($i + 1) % 5 -eq 0) {
                $elapsed = ($i + 1) * 2
                Write-Host ("[Demo] Docker not ready yet... {0}s" -f $elapsed) -ForegroundColor DarkYellow
            }
            cmd /c "docker info >nul 2>nul"
            if ($LASTEXITCODE -eq 0) {
                $ready = $true
                break
            }
        }

        if (-not $ready) {
            Write-Host '[Demo] Docker Desktop startup timeout. Please ensure Docker is Running, then retry.' -ForegroundColor Red
            exit 1
        }

        Write-Host '[Demo] Docker Desktop is ready.' -ForegroundColor Green
    } else {
        Write-Host '[Demo] Docker Desktop is not running (or docker command is unavailable).' -ForegroundColor Red
        Write-Host '[Demo] Please install/start Docker Desktop, then run start-demo.bat again.' -ForegroundColor Yellow
        exit 1
    }
}

Write-Host '[Demo] Starting Docker services...' -ForegroundColor Cyan
docker compose -f "$ScriptDir/docker-compose.demo.yml" up -d --build

Write-Host '[Demo] Waiting 8 seconds for container warm-up...' -ForegroundColor Cyan
Start-Sleep -Seconds 8

Write-Host '[Demo] Running end-to-end demo...' -ForegroundColor Cyan
py -3 "$ScriptDir/demo_runner.py"

if ($LASTEXITCODE -eq 0) {
    Write-Host '[Demo] All done. You can now record with one click flow evidence.' -ForegroundColor Green
} else {
    Write-Host '[Demo] Demo runner failed.' -ForegroundColor Red
    exit $LASTEXITCODE
}
