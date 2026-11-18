# 05 --- Testing and Quality Gates

## 1. Testing objective

The rebuild must improve the reliability of the whole workflow, not just
make individual functions pass tests. Every critical stage should have
automated coverage plus a small set of real-media regression fixtures.

## 2. Test layers

### Unit tests

Test pure logic: - timestamp validation and conversion; - clip duration
calculations; - candidate ranking signals; - caption layout
constraints; - project schema validation; - project migrations; - export
configuration generation; - error-code mapping.

### Integration tests

Test module boundaries: - project save/load; - transcription adapter
output normalization; - candidate generation from transcript fixtures; -
FFmpeg invocation and result parsing; - output metadata validation; -
cancellation/retry state transitions.

### End-to-end tests

At minimum: - import a supported fixture; - produce/load transcript
fixture; - generate or load candidate fixture; - edit boundaries and
captions; - export; - validate output duration, dimensions, audio, and
caption configuration; - reopen project and verify edits persist.

Where full AI inference is too slow or nondeterministic for every CI
run, use stable transcript/candidate fixtures for core workflow tests
and keep a smaller scheduled integration test for the real model.

## 3. Media fixture set

Maintain legally usable, small fixtures: - speech with clear audio; -
speech with moderate background noise; - more than one speaker; -
portrait and landscape input; - no-audio or silent input; - very short
video; - longer video representative of real use; - variable frame rate
or unusual media metadata if supported; - corrupt or unsupported file.

Record fixture provenance and permission. Keep CI fixtures small enough
to run predictably.

## 4. Export validation

After export: - file exists and is non-zero; - output can be probed and
decoded; - duration is within an explicit tolerance of expected
duration; - dimensions match the selected preset; - expected audio
stream exists when applicable; - no unexpected empty output; - caption
burn-in/subtitle behavior matches the selected mode; - output can be
played in a standard media player during manual regression.

A successful FFmpeg exit code alone is not sufficient proof of a valid
export.

## 5. Reliability requirements

-   Failed stages produce actionable errors.
-   Retrying a failed stage does not duplicate or corrupt project
    records.
-   Temporary files are cleaned up safely.
-   Cancellation leaves project data in a consistent state.
-   A crash during export should not mark a partial file as completed.
-   The application can reopen a project after interrupted processing.
-   Processing state transitions are validated (e.g. a completed job
    cannot return to running without a new attempt).

## 6. Performance tests

Measure representative workloads on the actual development machine: -
time to probe; - time to transcribe per source minute; - time to
generate candidates; - time to export per source minute; - peak RAM; -
CPU/GPU utilization where available; - output file size; - thermal or
sustained-load concerns for long jobs.

Use median and tail values across repeated runs; a single best-case
measurement is misleading. Keep the hardware and model configuration
with the results.

## 7. UI and usability tests

Manually test: - empty state; - loading/progress state; - recoverable
failure; - invalid input; - long filenames and paths; - project
reopen; - edits while a job is running; - window resize/small
viewport; - keyboard and focus behavior; - export path and success
notification.

Use observed usability sessions. Ask users to perform tasks without
coaching and note where they hesitate or make mistakes.

## 8. CI quality gates

Suggested minimum gates: - formatting and linting; - type checking where
supported; - unit tests; - integration tests that do not require
expensive inference; - build succeeds; - no secrets in the repository; -
project schema migration tests; - end-to-end smoke test with small media
fixture.

Do not block every change on a large, expensive model run. Keep
expensive integration tests separate and run them on a schedule or
before releases.

## 9. Regression checklist for each release

-   [ ] Import supported file.
-   [ ] Handle unsupported/corrupt file.
-   [ ] Generate/load transcript.
-   [ ] Generate/load candidates.
-   [ ] Accept and reject candidates.
-   [ ] Trim clip and reset to suggested boundaries.
-   [ ] Correct caption text.
-   [ ] Change caption style and position.
-   [ ] Adjust crop if available.
-   [ ] Preview edited clip.
-   [ ] Export MP4.
-   [ ] Verify dimensions, duration, audio, and captions.
-   [ ] Reopen project and confirm edit persistence.
-   [ ] Retry after a simulated failure.
-   [ ] Confirm source media was not modified.
-   [ ] Confirm logs contain no secrets or unnecessary personal data.

## 10. Definition of done for a feature

A feature is done only when: - acceptance criteria are met; - code has
been reviewed; - tests cover normal and important failure paths; -
user-visible errors are understandable; - documentation is updated; -
performance and privacy implications are considered; - the feature does
not break the import-to-export workflow.
