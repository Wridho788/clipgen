param(
    [Parameter(Mandatory = $true)]
    [string]$ArchivePath,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $Force) {
    throw "Restore replaces backend\storage. Run again with -Force after confirming the archive path."
}

$archive = Resolve-Path -LiteralPath $ArchivePath -ErrorAction Stop
$storagePath = Join-Path $root "backend\storage"
$stagingPath = Join-Path $root ("backend\storage-restore-" + [guid]::NewGuid().ToString("N"))

New-Item -ItemType Directory -Force -Path $stagingPath | Out-Null
try {
    Expand-Archive -LiteralPath $archive -DestinationPath $stagingPath -Force
    $hasDatabase = Test-Path -LiteralPath (Join-Path $stagingPath "app.db")
    if (-not $hasDatabase) {
        throw "Archive does not contain app.db and is not a valid ClipGen storage backup."
    }

    & "$PSScriptRoot\backup-storage.ps1"
    foreach ($name in @("app.db", "uploads", "clips", "temp")) {
        $target = Join-Path $storagePath $name
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
    Get-ChildItem -LiteralPath $stagingPath -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $storagePath -Recurse -Force
    }
    Write-Host "Storage restored. Restart backend before using ClipGen." -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $stagingPath) {
        Remove-Item -LiteralPath $stagingPath -Recurse -Force
    }
}
