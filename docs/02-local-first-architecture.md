# 02 --- Local-First Architecture

## 1. Architecture objective

Build a modular system that can run locally without requiring paid cloud
infrastructure for the normal development workflow. Keep external
services behind interfaces so they can be added later without rewriting
the product.

**Important:** this is a target architecture, not a claim about the
current repository. Audit the existing stack and preserve useful modules
before deciding how to migrate.

## 2. High-level logical architecture

``` text
UI / Project Workspace
        |
        v
Application Use Cases
  |       |        |
  v       v        v
Project  Clip     Export
Store    Analysis Pipeline
  |       |        |
  |       v        v
  |   Transcript  FFmpeg / Media
  |   Provider    Processing
  |       |
  v       v
Local Project Data + Source Media + Generated Assets
```

Suggested module boundaries: - **UI:** project list, import flow,
candidate review, editor, export status. - **Application layer:**
orchestrates use cases and owns workflow transitions. - **Project
domain:** project, source asset, transcript segment, clip candidate,
edit settings, export job. - **Storage adapter:** local
database/filesystem; future cloud storage adapter if justified. -
**Transcription adapter:** local model/provider; optional external
provider in the future. - **Candidate analysis:** segmentation, ranking,
explanations, evaluation instrumentation. - **Media adapter:** metadata
probing, thumbnails, waveform, preview support, FFmpeg export. -
**Observability:** structured logs, durations, error codes, resource
measurements.

Do not make UI components call FFmpeg, transcription libraries, or
database internals directly. Route those operations through a
well-defined application/service boundary.

## 3. Local-first principles

-   Source media remains at its original location or is copied only with
    explicit user understanding.
-   Keep generated assets in a predictable project workspace.
-   Store edit decisions as project data; do not repeatedly modify the
    source video.
-   Avoid uploading media or transcripts by default.
-   Avoid storing API keys in source code, project exports, or logs.
-   Provide a clear way to delete project data and generated assets.
-   Document whether deleting a project also deletes generated files and
    whether original media is preserved.

## 4. Project workspace

A possible project layout (adapt to the current app and operating
system):

``` text
ClipGenProjects/
  <project-id>/
    project.json
    media/
      source-reference.json
      thumbnails/
      waveform/
    transcript/
      transcript.json
    candidates/
      candidates.json
    exports/
      clip-001.mp4
    logs/
      processing.log
```

If the application supports a database, use it for structured metadata
and use the filesystem for large media artifacts. Do not put large video
blobs in a simple JSON project file.

## 5. Core domain entities

### Project

-   `id`
-   `name`
-   `createdAt`, `updatedAt`
-   `sourceAssetId`
-   `schemaVersion`
-   `status`

### SourceAsset

-   `id`
-   `path` or managed local URI
-   `fileName`
-   `durationMs`
-   `width`, `height`
-   `frameRate`
-   `audioPresent`
-   `fileSizeBytes`
-   `probeStatus`

### TranscriptSegment

-   `id`
-   `startMs`, `endMs`
-   `text`
-   optional speaker identifier
-   optional confidence if supplied by the transcription engine
-   `sourceProvider`, `modelVersion`

### ClipCandidate

-   `id`
-   `startMs`, `endMs`
-   `transcriptSegmentIds` or transcript snapshot
-   `rankingSignals`
-   `explanation`
-   `status` (suggested, accepted, rejected, edited, exported)
-   `algorithmVersion`

### ClipEdit

-   `clipId`
-   `trimStartMs`, `trimEndMs`
-   crop/framing parameters
-   caption settings
-   audio settings
-   output preset
-   edit schema version

### ExportJob

-   `id`
-   `clipId`
-   status (queued, running, completed, failed, cancelled)
-   progress if available
-   output path
-   error code and sanitized message
-   startedAt, completedAt
-   render configuration snapshot

Use integer milliseconds for timeline data to avoid inconsistent
floating-point time calculations. Convert to seconds or FFmpeg time
strings at the adapter boundary.

## 6. Versioning and migrations

-   Every persisted project should include a schema version.
-   Validate project data when loading.
-   Provide explicit migrations when schema changes.
-   Keep old project files recoverable where feasible.
-   Never silently discard unknown fields during load/save unless the
    migration explicitly requires it.
-   Add tests for every migration path.
-   Version candidate algorithms separately from project schema.

## 7. Processing pipeline

Recommended logical stages: 1. Validate file and probe metadata. 2.
Extract or decode audio as needed. 3. Transcribe with timestamps. 4.
Normalize transcript representation. 5. Generate candidate segments. 6.
Rank candidates and attach explanations. 7. Generate review assets such
as thumbnails/waveforms if supported. 8. Let the user edit the project.
9. Build a render configuration snapshot. 10. Run export. 11. Validate
output file and metadata. 12. Mark export complete and record
measurements.

Each stage should have a visible status, a clear error, and a retry
strategy. Cache reusable outputs such as transcripts when the source and
relevant model/settings have not changed.

## 8. Job execution

Even for a local app, treat long-running work as jobs rather than
blocking the UI thread.

-   UI submits a job and receives a stable job ID.
-   A worker performs the task.
-   Progress is reported when reliable progress information exists.
-   Cancellation is supported only where the operation can stop safely.
-   The user can navigate away without losing project state.
-   Errors include a stable internal code plus a human-readable
    explanation.
-   Avoid displaying fake progress percentages when the underlying
    process cannot report them.

If the current architecture is a web app, determine whether a local
worker is practical. Browser-only processing, a local companion process,
and a desktop wrapper have different security and deployment
implications. Do not choose among them until the current stack and
requirements are audited.

## 9. Media rendering and preview parity

Create one canonical edit representation consumed by both preview and
export.

The edit representation should capture: - source in/out points; - output
width/height and frame rate; - crop/framing; - caption text, timing,
style, and placement; - audio behavior; - codec/container preset.

Preview may use a faster approximation, but must communicate any known
discrepancy. Export must use the saved project state, not transient UI
values.

Add parity tests that compare: - output duration to expected duration; -
frame dimensions and aspect ratio; - caption presence and rough
placement; - audio presence; - trim boundaries within an explicitly
chosen tolerance.

## 10. FFmpeg considerations

-   Invoke FFmpeg through a controlled adapter with argument arrays
    rather than shell-concatenated user input.
-   Validate and normalize paths.
-   Capture exit code and sanitized stderr for diagnostics.
-   Use temporary output files and atomically move completed files into
    their final path where supported.
-   Verify output existence, non-zero size, and probeable metadata after
    rendering.
-   Document the exact FFmpeg build and enabled components before
    distributing the application; licensing obligations depend on build
    configuration and dependencies.
-   Do not assume one set of codec flags works on every operating
    system. Maintain a tested preset matrix.

## 11. Performance and resource management

Record: - source duration and size; - transcription wall time; -
candidate-generation wall time; - export wall time; - peak memory where
available; - CPU/GPU usage where practical; - output size; - failure
code.

Test short, medium, and long sources on the actual development hardware.
Set practical limits and provide warnings instead of allowing a huge
source file to freeze the experience.

## 12. Future cloud migration seam

Do not build cloud complexity prematurely. Keep these replaceable
interfaces: - `TranscriptionProvider` - `MediaStorage` -
`RenderExecutor` - `JobQueue` - `ProjectRepository` - `TelemetrySink`

A later cloud architecture may move heavy rendering to a worker service
while retaining the same project/edit schema. Avoid tying project data
to local absolute paths; use asset references that can be remapped
during import or upload.

## 13. Security and privacy

-   Never execute a user-supplied filename as a command.
-   Do not trust MIME type or file extension alone.
-   Validate file size, metadata, and decoding behavior.
-   Protect against path traversal when creating project/export paths.
-   Sanitize logs and never log secrets.
-   Make external processing opt-in and explain what data leaves the
    device.
-   Test deletion behavior for cached transcripts, thumbnails, and
    temporary files.
