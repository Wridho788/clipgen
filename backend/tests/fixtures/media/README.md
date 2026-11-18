# Media fixtures

Small, legally clean media for backend integration tests, the real-stack
end-to-end check (`scripts/e2e_real.py`), and the Playwright editor specs.
Regenerate with `pwsh scripts/make-media-fixtures.ps1` (Windows; needs
FFmpeg on PATH). Regenerated files are equivalent, not byte-identical.

| File | Content | Purpose |
|---|---|---|
| `speech_landscape.mp4` | 103.9 s, 480×270, 15 fps, mono AAC. Podcast-style monologue (15 sentences, one question, natural pauses). | Main workflow fixture: transcription, candidates, captions, renders. |
| `speech_landscape.transcript.json` | faster-whisper `tiny` output for the file above, recorded 2026-10-10. Includes two hallucinated segments past the end of the audio. | Deterministic transcript for pipeline tests; normalization regression. |
| `speech_portrait.mp4` | 16.5 s, 270×480, second voice. | Portrait input, short source. |
| `no_audio.mp4` | 8 s video, no audio stream. | `AUDIO_MISSING`, silent exports. |
| `very_short.mp4` | 3 s with a sine tone. | Shorter than the minimum clip (`CANDIDATE_EMPTY` warning). |
| `corrupt.mp4` | 4 KB of seeded random bytes. | `SOURCE_CORRUPT`. |

## Provenance and permission

- Speech: synthesized locally with Microsoft Windows SAPI voices
  ("Microsoft David Desktop", "Microsoft Zira Desktop") from text written
  for this repository. No external service, no third-party recordings.
- Video: FFmpeg `testsrc2` test pattern; audio tone: FFmpeg `sine`.
- No personal data. Safe to commit and to use in CI.
