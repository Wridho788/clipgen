param(
    [string]$OutputDir = "release-artifacts\backups"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$storagePath = Join-Path $root "backend\storage"
if (-not (Test-Path -LiteralPath $storagePath)) {
    throw "Storage directory not found: $storagePath"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputPath = Join-Path $root $OutputDir
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

$archivePath = Join-Path $outputPath "clipgen-storage-$timestamp.zip"
Compress-Archive -Path (Join-Path $storagePath "*") -DestinationPath $archivePath -CompressionLevel Optimal

Write-Host "Storage backup created:" -ForegroundColor Green
Write-Host $archivePath
