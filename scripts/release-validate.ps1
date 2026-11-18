param(
    [int]$FrontendPort = 3001,
    [string]$BackendUrl = "http://localhost:8000",
    [switch]$SkipPlaywrightInstall,
    # Real Whisper/FFmpeg/Ollama workflow (several minutes): scripts/e2e_real.py
    [switch]$RunRealE2E
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Assert-File {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required release file missing: $Path"
    }
}

Write-Host "Running release validation..." -ForegroundColor Cyan

Assert-File "README.md"
Assert-File "docs/README.md"
foreach ($doc in @(
    "01-product-requirements.md", "02-local-first-architecture.md", "03-editor-experience.md",
    "04-clipping-quality-and-evaluation.md", "05-testing-and-quality-gates.md", "06-90-day-roadmap.md",
    "07-decisions-and-open-questions.md", "08-repository-audit.md", "09-baseline-report.md",
    "10-implementation-notes.md"
)) { Assert-File "docs/$doc" }
Assert-File "backend/tests/fixtures/media/speech_landscape.mp4"
Assert-File "scripts\sprint3-validate.ps1"
Assert-File "scripts\e2e_real.py"
Assert-File "scripts\eval_report.py"
Assert-File "scripts/backup-storage.ps1"
Assert-File "scripts/restore-storage.ps1"
Assert-File "scripts\export-release-package.ps1"

$env:FRONTEND_HOST_PORT = [string]$FrontendPort
Write-Host ""
Write-Host "== Build release Docker images ==" -ForegroundColor Cyan
docker compose up -d --build backend frontend

$sprint3Args = @{
    FrontendPort = $FrontendPort
    BackendUrl = $BackendUrl
}
if ($SkipPlaywrightInstall) {
    $sprint3Args.SkipPlaywrightInstall = $true
}
& "$PSScriptRoot\sprint3-validate.ps1" @sprint3Args

$release = Invoke-RestMethod -Uri "$BackendUrl/api/system/release"
if ($release.version -ne "1.0.0") {
    throw "Unexpected backend release version: $($release.version)"
}
if ($release.features.vertical_crop -ne $true) {
    throw "Release contract drift: vertical_crop should be true."
}
if ($release.features.youtube_automatic_multi_clip -ne $true) {
    throw "Release contract drift: automatic YouTube multi-clip should be enabled."
}

$rootPackage = Get-Content package.json | ConvertFrom-Json
$frontendPackage = Get-Content frontend/package.json | ConvertFrom-Json
if ($rootPackage.version -ne "1.0.0" -or $frontendPackage.version -ne "1.0.0") {
    throw "Package versions must be 1.0.0 for the MVP release."
}

if ($RunRealE2E) {
    Write-Host ""
    Write-Host "== Real-stack end-to-end (Whisper + FFmpeg + Ollama) ==" -ForegroundColor Cyan
    python scripts/e2e_real.py --api $BackendUrl
    if ($LASTEXITCODE -ne 0) { throw "Real end-to-end check failed" }
}

Write-Host ""
Write-Host "Release validation completed." -ForegroundColor Green
