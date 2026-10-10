param(
    [string]$Version = "1.0.0",
    [string]$OutputDir = "release-artifacts"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$releaseRoot = Join-Path $root $OutputDir
$packageDir = Join-Path $releaseRoot "clipgen-v$Version-$timestamp"
$docsDir = Join-Path $packageDir "docs"
New-Item -ItemType Directory -Force -Path $docsDir | Out-Null

$files = @(
    "README.md",
    "docker-compose.yml",
    ".env.example"
) + (Get-ChildItem -Path "docs" -Filter "*.md" | ForEach-Object { "docs/$($_.Name)" }) + @("docs/eval/README.md")

foreach ($file in $files) {
    if (Test-Path -LiteralPath $file) {
        Copy-Item -LiteralPath $file -Destination $docsDir
    } else {
        Write-Warning "Release document not found: $file"
    }
}

$manifest = [ordered]@{
    name = "ClipGen"
    version = $Version
    created_at = (Get-Date).ToString("o")
    backend_url = "http://localhost:8000"
    frontend_url = "http://localhost:3001"
    validation_command = ".\scripts\release-validate.ps1 -SkipPlaywrightInstall -RunRealE2E"
    backup_command = ".\scripts\backup-storage.ps1"
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $packageDir "manifest.json")

$archivePath = Join-Path $releaseRoot "clipgen-v$Version-$timestamp.zip"
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $archivePath -CompressionLevel Optimal

Write-Host "Release package created:" -ForegroundColor Green
Write-Host $archivePath
