# 04 --- Clipping Quality and Evaluation

## 1. Why this document exists

An internal score above 100% did not result in the expected view count
in earlier tests. This means the score must not be treated as proof of
quality or a prediction of distribution.

A short video can underperform because of: - weak or incomplete moment
selection; - unclear context or missing setup; - poor opening/hook; -
bad start/end boundaries; - incorrect captions; - poor crop or audio; -
mismatch with the target audience; - publishing time, account history,
competition, platform distribution, or other factors outside ClipGen.

The evaluation process should distinguish product-controlled quality
from audience outcomes.

## 2. Quality dimensions

Use a human rubric for each candidate. Rate each dimension 1--5, with
explicit examples for the team.

1.  **Standalone clarity:** can a viewer understand the moment without
    the full source?
2.  **Context completeness:** does the clip preserve enough setup to
    make the point coherent?
3.  **Opening strength:** does the opening quickly establish a
    meaningful question, claim, conflict, or payoff?
4.  **Boundary quality:** does it begin and end at natural points
    without cutting a word or thought?
5.  **Value/interest:** does the moment offer insight, entertainment,
    surprise, or useful information for the intended audience?
6.  **Caption accuracy:** are the words correct enough to preserve
    meaning?
7.  **Visual readability:** is the subject framed well and are captions
    readable?
8.  **Audio quality:** is speech audible and not unintentionally
    clipped?
9.  **Pacing:** does the clip avoid long dead sections without cutting
    meaningful pauses or context?
10. **Policy/rights review:** is the content appropriate for the
    intended publishing context and does the user have rights to
    repurpose it?

A high score on one dimension must not hide a critical failure in
another. For example, a strong hook does not compensate for an
unintelligible or contextless clip.

## 3. Labeling protocol

For a small initial evaluation: - Select 10--20 representative source
videos, subject to lawful access and permission. - Include different
durations, speakers, recording quality, speaking pace, and topic
types. - Sample candidates from both high and low internal scores. -
Have a human review candidates using the same rubric. - If possible,
have a second reviewer independently rate a subset to detect
inconsistent labels. - Record the algorithm version and transcription
model/version used. - Keep source/video identifiers and labels organized
without publishing private material.

Do not select only videos where the algorithm already performs well.

## 4. Metrics

### Candidate-level

-   **Acceptance rate:** accepted or exported candidates / reviewed
    candidates.
-   **Rejection reasons:** context missing, weak moment, bad boundaries,
    transcript error, repeated content, poor crop, other.
-   **Boundary correction:** how often and how far users adjust
    start/end timestamps.
-   **Caption correction rate:** proportion of clips needing material
    caption correction.
-   **Human-vs-score association:** whether higher ranking signals
    correlate with human rubric ratings.
-   **Critical failure rate:** proportion with an issue that makes the
    clip unusable without substantial correction.

### Workflow-level

-   Time from import to first candidate.
-   Time from candidate selection to export.
-   Number of manual actions/corrections per exported clip.
-   Export success rate.
-   Repeat project creation within 14 days.
-   Percentage of testers who complete the workflow without help.

### Audience-level (separate)

When platform analytics are available and collection is appropriate: -
views at a consistent elapsed time after publishing; - average watch
duration or retention; - completion rate where available; - engagement
measures available from the platform; - topic, source, posting time,
account context, and format.

Do not compare raw view counts across unrelated accounts or topics as if
they were controlled experiments. A single low-view upload does not
prove the clip was poor; a single viral upload does not prove the score
works.

## 5. Calibrating the score

1.  Define what the score means. Prefer a relative ranking score over a
    claimed probability.
2.  List each input signal and its intended effect.
3.  Remove duplicated or highly correlated signals where they create
    false confidence.
4.  Compare score bands with human labels.
5.  Inspect false positives: high-scoring clips that reviewers reject.
6.  Inspect false negatives: lower-scoring clips reviewers consider
    strong.
7.  Adjust weights/thresholds and version the algorithm.
8.  Re-evaluate on videos not used to tune the scoring logic.

Never label a score as "chance of going viral" without a suitable
dataset, clear outcome definition, and calibration evidence.

## 6. Candidate selection principles

A candidate should ideally: - preserve a complete thought or story; -
start near the beginning of the meaningful moment, not after the key
setup; - end after the payoff or conclusion; - avoid cutting speech at
either boundary; - be short enough for the intended format without
removing necessary context; - avoid near-duplicate clips from the same
source; - include enough transcript context to explain why it was
selected.

The correct duration is content-dependent. Do not force every clip to
the same duration solely to satisfy a default.

## 7. Failure taxonomy

Use consistent internal reason codes: - `SOURCE_UNSUPPORTED` -
`SOURCE_CORRUPT` - `AUDIO_MISSING` - `TRANSCRIPTION_FAILED` -
`TRANSCRIPT_TIMESTAMPS_INVALID` - `CANDIDATE_EMPTY` -
`CANDIDATE_BOUNDARY_INVALID` - `CANDIDATE_CONTEXT_WEAK` -
`CAPTION_ALIGNMENT_POOR` - `PREVIEW_FAILED` - `EXPORT_FAILED` -
`EXPORT_VALIDATION_FAILED` - `RESOURCE_LIMIT_EXCEEDED` - `UNKNOWN`

Show a human-readable message in the UI and retain sanitized technical
details for debugging.

## 8. Definition of "good enough"

Do not define quality only by views. For an initial beta, a practical
internal release gate can be: - no known systematic timestamp
corruption; - most tested sources produce candidates without manual
pipeline intervention; - a clear majority of reviewed candidates are at
least usable starting points, as measured by the team's rubric; -
critical caption and export defects are below an explicitly chosen
tolerance; - users can reject/edit candidates and still complete
export; - score ranking shows useful alignment with human judgments, or
is clearly presented as an experimental heuristic.

Set numeric thresholds after the baseline audit. Avoid inventing
precision before measurements exist.
