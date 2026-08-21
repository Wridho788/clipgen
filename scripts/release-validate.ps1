param(
    [int]$FrontendPort = 3001,
    [string]$BackendUrl = "http://localhost:8000",
    [switch]$SkipPlaywrightInstall
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

Write-Host "Running Sprint 4 release validation..." -ForegroundColor Cyan

Assert-File "README.md"
Assert-File "RELEASE_NOTES.md"
Assert-File "RELEASE_CHECKLIST.md"
Assert-File "SPRINT4_RELEASE_READINESS.md"
Assert-File "SPRINT3_QA_CHECKLIST.md"
Assert-File "scripts\sprint3-validate.ps1"
Assert-File "scripts\backup-storage.ps1"
Assert-File "scripts\restore-storage.ps1"
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
if ($release.features.youtube_subtitles -ne $true) {
    throw "Release contract drift: youtube_subtitles should be true."
}
if ($release.features.youtube_automatic_multi_clip -ne $true) {
    throw "Release contract drift: automatic YouTube multi-clip should be enabled."
}

$rootPackage = Get-Content package.json | ConvertFrom-Json
$frontendPackage = Get-Content frontend/package.json | ConvertFrom-Json
if ($rootPackage.version -ne "1.0.0" -or $frontendPackage.version -ne "1.0.0") {
    throw "Package versions must be 1.0.0 for the MVP release."
}

Write-Host ""
Write-Host "Sprint 4 release validation completed." -ForegroundColor Green
