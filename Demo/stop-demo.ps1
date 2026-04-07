$ErrorActionPreference = 'Continue'
Write-Host '[Demo] Stopping Docker services...' -ForegroundColor Yellow
docker compose -f "Demo/docker-compose.demo.yml" down -v
Write-Host '[Demo] Stopped and volumes removed.' -ForegroundColor Green
