param(
    [int]$FrontendPort = 3001,
    [string]$BackendUrl = "http://localhost:8000",
    [switch]$SkipFrontendBuild,
    [switch]$SkipPlaywrightInstall
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )
    Write-Host ""
    Write-Host "== $Name ==" -ForegroundColor Cyan
    & $Command
}

$env:FRONTEND_HOST_PORT = [string]$FrontendPort

Invoke-Step "Docker Compose config" {
    docker compose config --quiet
}

Invoke-Step "Start backend and frontend" {
    docker compose up -d backend frontend
}

Invoke-Step "Backend readiness" {
    curl.exe -f "$BackendUrl/health/ready"
}

Invoke-Step "Backend system metrics" {
    curl.exe -f "$BackendUrl/api/system/metrics"
}

Invoke-Step "Backend performance baseline" {
    curl.exe -f "$BackendUrl/api/system/performance"
}

Invoke-Step "Backend pytest in container (unit, API, real-FFmpeg media)" {
    # Tests are not baked into the image; copy them next to the mounted app
    # code with pytest.ini so markers, asyncio mode, and imports resolve.
    docker exec clipgen-backend rm -rf /app/tests
    docker cp backend/tests clipgen-backend:/app/tests
    docker cp backend/pytest.ini clipgen-backend:/app/pytest.ini
    docker exec -w /app clipgen-backend python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }
}

Invoke-Step "Backend static checks (ruff F/E9)" {
    docker exec -w /app clipgen-backend python -m ruff check app tests --select F,E9
    if ($LASTEXITCODE -ne 0) { throw "Ruff found errors" }
}

Invoke-Step "Frontend lint + type check" {
    pnpm --dir frontend lint
    if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed" }
    pnpm --dir frontend exec tsc --noEmit
    if ($LASTEXITCODE -ne 0) { throw "Frontend type check failed" }
}

if (-not $SkipFrontendBuild) {
    Invoke-Step "Frontend build" {
        pnpm --dir frontend build
    }
}

if (-not $SkipPlaywrightInstall) {
    Invoke-Step "Install Playwright Chromium" {
        pnpm --dir frontend exec playwright install chromium
    }
}

Invoke-Step "Frontend Playwright E2E" {
    $env:PLAYWRIGHT_BASE_URL = "http://localhost:$FrontendPort"
    $env:PLAYWRIGHT_SKIP_WEB_SERVER = "1"
    pnpm --dir frontend e2e
}

Invoke-Step "Manual cleanup endpoint smoke" {
    curl.exe -f -X POST "$BackendUrl/api/system/maintenance/cleanup"
}

Write-Host ""
Write-Host "Sprint 3 validation completed." -ForegroundColor Green
