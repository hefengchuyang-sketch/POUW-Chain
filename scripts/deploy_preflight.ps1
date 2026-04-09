param(
    [switch]$Strict,
    [switch]$CheckPythonDeps
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$issues = @()
$warnings = @()

function Add-Issue([string]$msg) {
    $script:issues += $msg
}

function Add-Warn([string]$msg) {
    $script:warnings += $msg
}

Write-Host "[1/5] Checking Docker CLI..."
try {
    $dockerVersion = docker --version 2>$null
    if (-not $dockerVersion) { Add-Issue "Docker CLI not found." }
} catch {
    Add-Issue "Docker CLI not found. Install Docker Desktop first."
}

Write-Host "[2/5] Checking Docker daemon..."
try {
    docker info 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) {
        Add-Issue "Docker daemon is not running. Start Docker Desktop."
    }
} catch {
    Add-Issue "Docker daemon is not running. Start Docker Desktop."
}

Write-Host "[3/5] Validating docker compose file..."
if (Test-Path "docker-compose.yml") {
    try {
        docker compose config 1>$null
        if ($LASTEXITCODE -ne 0) {
            Add-Issue "docker compose config failed. Check docker-compose.yml."
        }
    } catch {
        Add-Issue "docker compose command failed. Check Docker Compose plugin."
    }
} else {
    Add-Issue "docker-compose.yml not found in repository root."
}

Write-Host "[4/5] Checking production admin key..."
$adminKey = (Get-Item Env:POUW_ADMIN_KEY -ErrorAction SilentlyContinue).Value
if ([string]::IsNullOrWhiteSpace($adminKey)) {
    Add-Warn "POUW_ADMIN_KEY is empty. For production, set a strong admin key before deployment."
}

Write-Host "[5/5] Optional Python dependency check..."
if ($CheckPythonDeps) {
    try {
        $py = "python"
        & $py -c "import yaml, ecdsa, mnemonic, aiohttp" 1>$null 2>$null
        if ($LASTEXITCODE -ne 0) {
            Add-Issue "Python dependencies missing. Run: pip install -r requirements.txt"
        }
    } catch {
        Add-Issue "Python not available in PATH. Install Python 3.10+ or use conda python."
    }
}

Write-Host ""
if ($warnings.Count -gt 0) {
    Write-Host "Warnings:" -ForegroundColor Yellow
    foreach ($w in $warnings) {
        Write-Host " - $w" -ForegroundColor Yellow
    }
}

if ($issues.Count -gt 0) {
    Write-Host ""
    Write-Host "Deployment preflight failed:" -ForegroundColor Red
    foreach ($i in $issues) {
        Write-Host " - $i" -ForegroundColor Red
    }
    if ($Strict) { exit 1 }
    exit 2
}

Write-Host "Deployment preflight passed." -ForegroundColor Green
exit 0
