<#!
.SYNOPSIS
  Records a ClipGen job's live stages and final timing into a portable JSON file.

.EXAMPLE
  .\scripts\benchmark-job.ps1 -JobId d1beb422-d982-4620-8f9b-34580372ffa7
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)]
  [ValidatePattern('^[0-9a-fA-F-]{36}$')]
  [string]$JobId,

  [string]$ApiUrl = 'http://localhost:8000',

  [ValidateRange(5, 300)]
  [int]$PollSeconds = 30,

  [string]$OutputDirectory = (Join-Path $PSScriptRoot '..\benchmark-results')
)

$ErrorActionPreference = 'Stop'
$baseUrl = $ApiUrl.TrimEnd('/')
$startedAt = Get-Date
$samples = [System.Collections.Generic.List[object]]::new()

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

do {
  $job = Invoke-RestMethod -Uri "$baseUrl/api/jobs/$JobId" -Method Get
  $samples.Add([ordered]@{
      observed_at = (Get-Date).ToUniversalTime().ToString('o')
      status = $job.status
      progress = $job.progress
      current_stage_elapsed_seconds = $job.current_stage_elapsed_seconds
      current_stage_eta_seconds = $job.current_stage_eta_seconds
      overall_eta_seconds = $job.overall_eta_seconds
      heartbeat_at = $job.heartbeat_at
      stage_estimates = $job.stage_estimates
      stage_metrics = $job.stage_metrics
      runtime = $job.runtime
    })

  Write-Host ("[{0}] {1} {2}% | stage elapsed {3:n0}s | total ETA {4:n0}s" -f (Get-Date -Format 'HH:mm:ss'), $job.status, $job.progress, $job.current_stage_elapsed_seconds, $job.overall_eta_seconds)
  $terminal = $job.status -in @('done', 'failed', 'cancelled')
  if (-not $terminal) {
    Start-Sleep -Seconds $PollSeconds
  }
} while (-not $terminal)

$release = Invoke-RestMethod -Uri "$baseUrl/api/system/release" -Method Get
$endedAt = Get-Date
$sourceDuration = if ($null -ne $job.source_duration_seconds) {
  [double]$job.source_duration_seconds
} else {
  0
}
$wallSeconds = ($endedAt - $startedAt).TotalSeconds
$benchmark = [ordered]@{
  benchmark_version = 1
  job_id = $job.id
  started_at = $startedAt.ToUniversalTime().ToString('o')
  ended_at = $endedAt.ToUniversalTime().ToString('o')
  wall_seconds = [math]::Round($wallSeconds, 2)
  source = [ordered]@{
    type = $job.source_type
    duration_seconds = $sourceDuration
    size_bytes = $job.source_size_bytes
  }
  processing_options = $job.processing_options
  runtime = $release.acceleration
  final_status = $job.status
  final_progress = $job.progress
  stage_metrics = $job.stage_metrics
  stage_estimates = $job.stage_estimates
  transcription_rtf = if ($sourceDuration -gt 0 -and $job.stage_metrics.transcribing) {
    [math]::Round(([double]$job.stage_metrics.transcribing / $sourceDuration), 3)
  } else { $null }
  samples = $samples
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$destination = Join-Path $OutputDirectory "clipgen-$($job.id)-$stamp.json"
$benchmark | ConvertTo-Json -Depth 10 | Set-Content -Path $destination -Encoding utf8
Write-Host "Benchmark disimpan: $destination"
