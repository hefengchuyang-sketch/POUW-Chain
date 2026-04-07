$ErrorActionPreference = 'Continue'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
Set-Location $RepoRoot

docker info *> $null
if ($LASTEXITCODE -ne 0) {
	Write-Host '[Demo] Docker Desktop is not running. Nothing to stop.' -ForegroundColor Yellow
	exit 0
}

Write-Host '[Demo] Stopping Docker services...' -ForegroundColor Yellow
docker compose -f "$ScriptDir/docker-compose.demo.yml" down -v
Write-Host '[Demo] Stopped and volumes removed.' -ForegroundColor Green
