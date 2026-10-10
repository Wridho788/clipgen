<#
Generates the small, legally clean media fixtures used by backend
integration tests and the real-media end-to-end test.

Speech is synthesized locally with Windows SAPI (no external service);
video frames come from FFmpeg test sources. Re-running produces equivalent,
not byte-identical, files. See backend/tests/fixtures/media/README.md.
#>
param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\backend\tests\fixtures\media")
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force $OutputDir | Out-Null
$work = Join-Path ([System.IO.Path]::GetTempPath()) ("clipgen-fixtures-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force $work | Out-Null

function New-Speech([string]$Path, [string[]]$Lines, [string]$Voice) {
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $synth.SelectVoice($Voice)
    $synth.Rate = 0
    $synth.SetOutputToWaveFile($Path)
    foreach ($line in $Lines) {
        $synth.Speak($line)
        # Natural sentence-level pause so transcript segments have real gaps.
        $prompt = New-Object System.Speech.Synthesis.PromptBuilder
        $prompt.AppendBreak([TimeSpan]::FromMilliseconds(450))
        $synth.Speak($prompt)
    }
    $synth.Dispose()
}

$podcast = @(
    "Welcome back to the show. Today we are talking about how small teams ship reliable software.",
    "So here is the question everyone asks me. Why do most side projects never launch?",
    "The honest answer is that people build features before they build a habit of finishing.",
    "When I started, I rewrote my app three times. Each rewrite felt productive, but nobody ever used it.",
    "What changed everything was a simple rule. Ship one small thing every single week.",
    "That rule forced me to cut scope, write tests for the risky parts, and talk to real users.",
    "Let me give you a concrete example from last month.",
    "We had a video export bug that only happened on long files. Instead of guessing, we measured it.",
    "It turned out the encoder was fine. The real problem was a timestamp rounding error of a few milliseconds.",
    "Fixing that took ten minutes. Finding it took two days, because we had no logs.",
    "So my advice is this. Before you optimize anything, make the failure visible.",
    "Another mistake I see is trusting a single score. A high score does not mean people will watch.",
    "You have to look at what viewers actually do, and you have to accept that luck plays a part.",
    "If you remember one thing from this episode, remember this. Finish small, measure honestly, and keep going.",
    "Thanks for listening, and I will see you next week."
)
$podcastWav = Join-Path $work "podcast.wav"
New-Speech $podcastWav $podcast "Microsoft David Desktop"

$shortLines = @(
    "Is it possible to edit captions without leaving the app? Yes, and here is how it works.",
    "You open the clip, fix the words, and export again. The original video is never changed."
)
$shortWav = Join-Path $work "short.wav"
New-Speech $shortWav $shortLines "Microsoft Zira Desktop"

$ff = @("-hide_banner", "-loglevel", "error", "-y")

# Landscape talking-head stand-in with audio (main E2E fixture).
& ffmpeg @ff -f lavfi -i "testsrc2=size=480x270:rate=15" -i $podcastWav `
    -shortest -c:v libx264 -preset veryfast -crf 38 -pix_fmt yuv420p `
    -c:a aac -b:a 64k -ac 1 -movflags +faststart (Join-Path $OutputDir "speech_landscape.mp4")

# Portrait source with audio.
& ffmpeg @ff -f lavfi -i "testsrc2=size=270x480:rate=15" -i $shortWav `
    -shortest -c:v libx264 -preset veryfast -crf 38 -pix_fmt yuv420p `
    -c:a aac -b:a 64k -ac 1 -movflags +faststart (Join-Path $OutputDir "speech_portrait.mp4")

# Video without any audio stream.
& ffmpeg @ff -f lavfi -i "testsrc2=size=640x360:rate=25" -t 8 `
    -c:v libx264 -preset veryfast -crf 34 -pix_fmt yuv420p (Join-Path $OutputDir "no_audio.mp4")

# Very short source (shorter than the minimum clip length).
& ffmpeg @ff -f lavfi -i "testsrc2=size=640x360:rate=25" -f lavfi -i "sine=frequency=440:sample_rate=16000" `
    -t 3 -c:v libx264 -preset veryfast -crf 34 -pix_fmt yuv420p -c:a aac -b:a 48k (Join-Path $OutputDir "very_short.mp4")

# Corrupt file: an MP4 extension over random bytes.
$bytes = New-Object byte[] 4096
(New-Object System.Random 42).NextBytes($bytes)
[System.IO.File]::WriteAllBytes((Join-Path $OutputDir "corrupt.mp4"), $bytes)

Remove-Item -Recurse -Force $work
Get-ChildItem $OutputDir -Filter *.mp4 | Select-Object Name, Length
