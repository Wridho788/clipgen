# 01 --- Product Requirements Document (PRD)

## 1. Product overview

ClipGen is a local-first tool that helps creators convert long-form
videos---initially podcast/interview-style material---into short
vertical clips suitable for platforms such as YouTube Shorts and
Facebook Reels.

The proposed product experience has two connected stages:

1.  **AI-assisted discovery:** analyze a source video and suggest
    candidate moments with timestamps, transcript context, and
    explainable reasons.
2.  **Human-controlled finishing:** let the user trim, correct captions,
    adjust vertical framing, preview, and export.

The user must be able to reject or edit AI output. AI suggestions are
drafts, not final truth.

## 2. Problem statement

Creators face several types of friction when turning long videos into
short clips:

-   Finding moments that are understandable without the full
    conversation.
-   Getting start/end boundaries right.
-   Making captions accurate and readable.
-   Reframing landscape footage into vertical format.
-   Repeating the same edits across multiple clips.
-   Exporting reliably without having to move to a separate editor for
    basic corrections.

ClipGen's previous internal score exceeding 100% did not guarantee that
published videos would reach 1,000 views. Therefore, the product must
not treat a high internal score as evidence of audience performance.
Clip quality and distribution performance are separate problems.

## 3. Product goal

Deliver a dependable workflow in which a user can go from a source video
to at least one acceptable, editable, exported short clip with minimal
tool switching.

### Primary outcome

A user can inspect an AI-generated candidate, make corrections, and
export a valid vertical MP4.

### Secondary outcomes

-   Candidate selection is more useful than random or fixed-length
    slicing.
-   Captions can be corrected and styled without editing source files.
-   Export output matches the editor preview closely.
-   Users can repeat the workflow on another source without relearning
    it.
-   Processing failures are visible, recoverable, and diagnosable.

## 4. Initial user hypothesis

Do not assume that "all video clipping users" are one coherent audience.
Start with one or two test cohorts and learn from their behavior.

Candidate cohorts to test: - Podcasters and interview creators
publishing weekly. - Educational creators with long explanations or
tutorials. - Social media operators repurposing content for clients.

These are hypotheses, not verified market findings. Select the first
cohort based on access to real testers and frequency of the problem, not
on intuition alone.

## 5. Product principles

1.  **Local-first:** local processing is the default while feasible;
    cloud services are optional future adapters.
2.  **User control:** every AI-selected clip can be reviewed and
    changed.
3.  **Explainability:** show why a clip was suggested; do not display an
    uncalibrated score as a probability of virality.
4.  **Reliable output:** preview and export should use the same edit
    decisions.
5.  **Recoverability:** failed processing must not destroy project state
    or source files.
6.  **Measurability:** track timings, failures, quality judgments, and
    repeat usage.
7.  **Modular design:** separate UI, project state, media processing,
    transcription, candidate ranking, and export.
8.  **Privacy by default:** local media stays local unless the user
    explicitly chooses an external service.

## 6. Scope and priorities

### P0 --- required for the core workflow

-   Create/open a project and select a local video file.
-   Validate supported formats and report unsupported/corrupt files
    clearly.
-   Extract source metadata (duration, dimensions, frame rate, audio
    presence).
-   Generate a transcript with timestamps using the current
    transcription engine or a replaceable adapter.
-   Generate candidate clips with start/end timestamps and transcript
    context.
-   Let users review, accept, reject, reorder, duplicate, and rename
    candidates.
-   Edit clip start/end times.
-   Edit caption text and timing where supported by the current
    architecture.
-   Configure basic caption style: font size, color, background/outline,
    and position.
-   Preview the clip in a 9:16 canvas.
-   Export MP4 with audio and captions/framing settings applied.
-   Show progress, errors, cancellation where safe, and retry.
-   Save project edits so a restart does not silently discard work.

### P1 --- high-value improvements after P0 is stable

-   Adjustable vertical crop and subject positioning.
-   Undo/redo for common editing actions.
-   Autosave with visible save status.
-   Reusable caption and brand presets.
-   Batch export of selected clips.
-   Keyboard shortcuts for trimming and playback.
-   Export presets for common social-video formats.
-   Better audio-level handling and optional normalization.
-   Basic performance diagnostics and processing logs.

### P2 --- defer until validated

-   Full multi-track editor comparable to a professional desktop editor.
-   Complex keyframes, transitions, advanced effects, and B-roll
    generation.
-   Built-in publishing/scheduling integrations.
-   Multi-user collaboration and hosted projects.
-   Subscription billing, team roles, and large-scale cloud queues.
-   Automatic promises or optimization claims tied to views/virality.

## 7. Functional acceptance criteria

### Import

-   User can select a local source file.
-   Invalid or unsupported input produces a useful error and does not
    crash the app.
-   Original source file is not modified.
-   Source metadata is saved to the project.

### Transcript

-   Transcript segments contain text and start/end timestamps.
-   Timestamp order is valid and does not extend beyond source duration.
-   Transcription errors can be retried without recreating the entire
    project.
-   The UI indicates whether the transcript is pending, processing,
    ready, or failed.

### Candidate generation

-   Every candidate has a stable ID, start/end times, transcript
    context, and status.
-   Start time is less than end time; times fall within source duration.
-   The system explains candidate reasons using signals actually
    available to the algorithm.
-   Score labels clearly state that the score is an internal ranking
    signal, not a view forecast.
-   Users can edit or discard every candidate.

### Editing and preview

-   Trim edits update project state immediately.
-   Caption text edits are reflected in preview.
-   Preview uses the same project edit data that export consumes.
-   Unsaved changes are clearly indicated or autosaved.
-   A failed render leaves the project editable and retryable.

### Export

-   Export produces a valid playable MP4 for the supported target
    preset.
-   Export dimensions and aspect ratio match the chosen preset.
-   Audio is present when the source contains audio and audio is
    enabled.
-   Captions and crop match the saved edit settings.
-   Export completion and failure are reported clearly.
-   Output path is visible and user-controlled or follows a clearly
    documented default.

## 8. Product metrics

Measure before optimizing. Initial targets below are internal
experiments, not industry benchmarks.

-   **Workflow completion:** users who successfully export / users who
    start a project.
-   **Export success rate:** successful exports / export attempts.
-   **Activation:** new testers who export at least one clip.
-   **Time to first export:** elapsed time from opening a source to
    successful export.
-   **Editing burden:** number of manual corrections per exported clip
    and time spent editing.
-   **Candidate acceptance rate:** candidates retained or exported /
    candidates shown.
-   **Repeat use:** testers who start a second project within 14 days.
-   **Usability:** users who can complete core workflow without direct
    assistance.
-   **Processing cost:** local CPU/GPU time, peak memory, storage
    footprint, and any external API cost per source-video minute.
-   **Audience outcomes:** views, retention, and engagement may be
    collected where available, but must not be conflated with product
    quality or attributed solely to ClipGen.

## 9. Product claims and messaging

Allowed: - "Find and edit short-video candidates from long videos." -
"AI-assisted clipping with manual control." - "Review, refine, and
export vertical clips."

Avoid until supported by evidence: - "Guaranteed viral clips." -
"Guaranteed 1,000+ views." - "Best AI clipping tool." - Any percentage
score that implies a calibrated probability without validation.

## 10. MVP release gate

Do not call the MVP ready merely because the UI looks complete. It must
pass: - A complete import-to-export workflow. - Core automated tests. -
A manual regression checklist. - Preview/export parity checks. - A small
evaluation set covering different video lengths, speakers, and audio
quality. - Recovery checks for failed transcription and failed
rendering. - A clear list of known limitations.
