# 03 --- Editor Experience Specification

## 1. Design objective

The editor should close the most common gap between AI-generated
candidates and publishable clips. It does not need to reproduce every
capability of CapCut. It must make the core workflow dependable and
efficient.

The guiding idea: **AI creates a draft; the user controls the final
result.**

## 2. Primary workflow

1.  Create a project.
2.  Import a local video.
3.  Review source metadata and processing requirements.
4.  Generate or load transcript.
5.  Generate candidate clips.
6.  Review candidate list and reasons.
7.  Open a candidate in the editor.
8.  Adjust in/out points.
9.  Correct captions and choose style.
10. Adjust vertical framing.
11. Preview.
12. Export.
13. Review export result and optionally return to edit.

A user should not have to restart transcription just to change caption
style or trim boundaries.

## 3. Suggested information architecture

-   **Projects:** recent projects, source status, last edit, export
    status.
-   **Import:** file selection, metadata, supported format guidance.
-   **Analyze:** transcription and candidate-generation status.
-   **Candidates:** list of candidate moments, transcript snippets,
    duration, reason, status.
-   **Editor:** vertical preview, timeline/trim controls, captions,
    framing, output settings.
-   **Exports:** completed files, failures, retry, open output location.

Do not put every control on one screen. Use progressive disclosure, but
keep common trim and caption controls easy to discover.

## 4. Candidate review screen

Each candidate should show: - start and end timestamp; - duration; -
transcript excerpt; - reason(s) for selection; - quality/ranking signals
that are actually computed; - status: suggested, accepted, rejected,
edited, exported.

Actions: - preview; - accept; - reject; - edit; - duplicate if useful; -
rename; - export selected candidates.

Avoid presenting an unexplained "viral score" or a score above 100% as a
probability. If using a normalized ranking score, document its scale and
state that it ranks candidates within the current algorithm rather than
predicting views.

## 5. Editor layout

A practical desktop-first layout: - Left: candidate/project context and
optional clip list. - Center: 9:16 preview canvas. - Bottom: source/clip
timeline with visible in/out points. - Right: selected settings panel
for captions, framing, and output.

For a smaller viewport, panels can collapse. The editor must preserve
the selected clip and edit state when the layout changes.

## 6. Trimming behavior

-   Display current in/out timestamps and final duration.
-   Keep start before end and both within source duration.
-   Provide a clear way to set a boundary from the current playhead.
-   Seeking and playback should not unexpectedly modify trim points.
-   Make it easy to reset to the AI-suggested boundaries.
-   Keep the source immutable.
-   Persist edits using integer milliseconds.
-   If snapping is offered, show or document the snapping behavior.
-   When an edit invalidates an existing caption timing range, use a
    documented policy (e.g. clamp, flag, or ask the user) rather than
    silently shifting text incorrectly.

## 7. Caption editing

P0: - edit text; - inspect timing; - choose readable size; - choose text
color; - enable background or outline; - adjust vertical placement; -
preview against the video.

Important behavior: - The preview and export must use the same caption
source data. - Long text should wrap predictably. - Avoid captions that
fall outside the safe area. - Provide a sensible default style that is
readable on mixed footage. - Never silently replace user-corrected text
when regenerating or refreshing analysis.

Later: - word-level highlighting; - caption templates; - per-speaker
styling; - karaoke-style animation; - multi-language subtitle editing.

## 8. Vertical framing

P0 can use a centered crop if that is reliable. P1 should add
user-controlled framing.

Framing controls should: - preserve a 9:16 output canvas; - allow
horizontal/vertical positioning or an equivalent draggable crop; -
prevent blank edges unless the user intentionally chooses a
background-fill mode; - keep preview and render geometry consistent; -
save framing in the edit model.

Automatic face/speaker tracking is a later capability. Do not promise
reliable tracking until tested on multiple speakers, cuts, occlusion,
and low-resolution footage.

## 9. Preview behavior

-   Playback, seek, and pause should be predictable.
-   Show the clip's actual intended output aspect ratio.
-   Preview should reflect trim, captions, and framing.
-   If preview is an approximation, disclose the limitation.
-   Avoid rendering a full-resolution final export on every minor
    change.
-   Debounce expensive preview updates where necessary, without making
    the UI feel unresponsive.
-   Preserve edit state when preview generation fails.

## 10. Export experience

Expose only settings the product can reliably support: - output preset
(initially one reliable 9:16 preset may be enough); - resolution; -
frame rate if supported; - caption inclusion/burn-in; - output
filename/location.

Show: - processing stage; - progress when real progress is available; -
cancellation behavior; - output path on success; - actionable error on
failure; - retry without losing edits.

Before export, validate required inputs and warn about unsupported media
or missing audio if relevant.

## 11. Undo, redo, and autosave

P0: ensure project edits persist and save status is visible. P1:
undo/redo for user-visible editing operations.

Autosave should: - avoid writing on every tiny playback tick; - save
meaningful edit changes; - indicate saving/unsaved/error states; -
recover from app restart where feasible; - not overwrite a newer project
version with stale asynchronous state.

Undo/redo should operate on edit state, not on destructive modifications
to the source media.

## 12. Accessibility and usability

-   Provide labels for icon-only controls.
-   Use keyboard focus states and logical tab order.
-   Ensure caption controls have sufficient contrast.
-   Do not rely on color alone to communicate processing status.
-   Keep common actions consistently placed.
-   Use plain-language error messages with optional technical detail.

## 13. Usability test tasks

Ask a tester to complete these without coaching: 1. Import a source
video. 2. Generate candidates. 3. Identify and reject a weak candidate.
4. Trim a candidate to a better boundary. 5. Correct one caption. 6.
Change caption style. 7. Adjust framing if available. 8. Export the
clip. 9. Find the exported file. 10. Reopen the project and confirm
edits persist.

Record completion, errors, assistance required, time to first export,
and user confidence. Do not rely only on "Do you like it?" feedback.
