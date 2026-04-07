$ErrorActionPreference = 'Stop'

Write-Host '[Demo] Starting Docker services...' -ForegroundColor Cyan
docker compose -f "Demo/docker-compose.demo.yml" up -d --build

Write-Host '[Demo] Waiting 8 seconds for container warm-up...' -ForegroundColor Cyan
Start-Sleep -Seconds 8

Write-Host '[Demo] Running end-to-end demo...' -ForegroundColor Cyan
py -3 "Demo/demo_runner.py"

if ($LASTEXITCODE -eq 0) {
    Write-Host '[Demo] All done. You can now record with one click flow evidence.' -ForegroundColor Green
} else {
    Write-Host '[Demo] Demo runner failed.' -ForegroundColor Red
    exit $LASTEXITCODE
}
