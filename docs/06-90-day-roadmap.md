# 06 --- 90-Day Roadmap

## Operating assumptions

-   Development and early processing are local-first.
-   Existing Claude and Codex subscriptions are available for
    development assistance, subject to their plan limits and terms.
-   No new paid infrastructure is assumed initially.
-   Current codebase condition and feature completeness have not yet
    been audited.
-   Day ranges are planning windows, not promises; change them when
    evidence shows a different priority.

## Phase 0 --- Repository and product audit (Days 1--7)

### Work

-   Map current app structure, dependencies, entry points, and run/build
    commands.
-   Inventory completed, partial, and broken features.
-   Identify duplicate modules and fragile coupling.
-   Run the current app end-to-end and record baseline behavior.
-   Capture 3--5 representative source videos and current outputs, with
    appropriate rights/permissions.
-   Record known bugs, average processing times, and export failures.
-   Review security, secrets, temporary files, and external service
    usage.

### Deliverables

-   Architecture map.
-   Feature inventory: keep, refactor, replace, remove.
-   Baseline quality report.
-   Prioritized issue list.
-   Migration plan that avoids unnecessary full rewrite.

### Gate

Do not begin a sweeping rewrite until the team can explain what
currently works, what fails, and why the proposed change is safer or
more useful.

## Phase 1 --- Stabilize the core pipeline (Days 8--21)

### Work

-   Normalize project/source/transcript/candidate/edit data.
-   Make timestamps and state transitions consistent.
-   Stabilize import and metadata probing.
-   Make transcription failures recoverable.
-   Add stable candidate IDs, valid boundaries, and explicit candidate
    statuses.
-   Add structured error codes and timing logs.
-   Add automated tests around the highest-risk logic.

### Deliverables

-   Stable source-to-candidate path.
-   Versioned project representation or a documented migration strategy.
-   Failure taxonomy.
-   Unit/integration test baseline.

### Gate

Representative inputs complete analysis without corrupting project
state; failures are explainable and retryable.

## Phase 2 --- Make editing usable (Days 22--42)

### Work

-   Implement dependable trim controls.
-   Implement caption text/style editing.
-   Ensure preview uses canonical edit state.
-   Implement basic 9:16 preview.
-   Implement export using the same edit configuration.
-   Validate exported media after rendering.
-   Add visible progress/error/retry states.
-   Persist edits and recover projects after restart.

### Deliverables

-   End-to-end editable export.
-   Editor usability test notes.
-   Preview/export parity report.
-   Known limitations list.

### Gate

A tester can import, generate/load a candidate, edit it, preview it,
export it, and reopen the project without developer intervention.

## Phase 3 --- Measure clipping quality (Days 43--56)

### Work

-   Build a labeled evaluation set from 10--20 representative source
    videos.
-   Review candidates using the rubric in
    `04-clipping-quality-and-evaluation.md`.
-   Compare score bands with human judgments.
-   Inspect false positives, false negatives, repeated clips, and
    boundary problems.
-   Improve ranking and boundary logic only where the data indicates a
    problem.
-   Version the candidate algorithm.

### Deliverables

-   Human-reviewed evaluation set.
-   Candidate acceptance/rejection report.
-   Score calibration report.
-   Prioritized quality fixes.

### Gate

ClipGen can explain what its score means, and the score is either shown
as a useful ranking signal or demoted until it is validated.

## Phase 4 --- Observed beta (Days 57--75)

### Work

-   Recruit 5--10 testers from one selected cohort; start smaller if
    recruitment is difficult.
-   Observe them completing tasks without coaching.
-   Record workflow completion, editing time, correction types, failure
    points, and repeat intent.
-   Ask testers to use ClipGen on their own real source material where
    rights allow.
-   Test willingness to pay through a concrete paid pilot or offer
    rather than a hypothetical question.

### Deliverables

-   Session observations.
-   Usability and activation metrics.
-   Feature requests separated from blockers.
-   Early evidence of repeat use and willingness to pay.

### Gate

External users can complete the workflow, at least some return to use it
again, and the team knows the top reasons for abandonment.

## Phase 5 --- Decide what to invest in next (Days 76--90)

### Work

-   Review all quality, usability, repeat-use, and cost data.
-   Calculate local resource needs and any external service cost per
    source-video minute.
-   Identify the most important bottleneck: quality, editor UX,
    processing speed, reliability, or demand.
-   Decide whether to continue local-first, add a small cloud worker, or
    narrow the product scope.
-   Prioritize no more than three major improvements for the next cycle.

### Deliverables

-   90-day decision memo.
-   Measured cost model.
-   Next-cycle roadmap.
-   Explicit continue/pivot/pause decision.

### Gate

Increase investment only when repeated use and meaningful user value are
supported by evidence, and the next bottleneck is measurable.

## Weekly operating rhythm

-   Monday: select the top one to three outcomes for the week.
-   During work: keep small changes, tests, and written decisions.
-   End of week: run regression, inspect metrics, list failures and open
    risks.
-   Every two weeks: test with a real person or real source video.
-   At each phase gate: decide based on evidence, not sunk cost.

## Decision rules

-   Users cannot finish editing/exporting → fix workflow
    reliability/usability first.
-   Candidates are consistently rejected → investigate segmentation,
    context, transcription, or ranking.
-   Candidates are accepted but need excessive manual correction →
    reduce correction burden.
-   Users like the output but do not return → investigate recurring
    need, workflow fit, and source frequency.
-   Users return but will not pay → test audience, positioning, price,
    and alternatives.
-   Costs are high before repeat demand exists → optimize or narrow the
    workload; do not scale blindly.
-   Users return and pay, and a measured bottleneck blocks growth →
    invest in the specific bottleneck.

## Initial internal targets

These are provisional experiment targets, not market benchmarks: -
Export completion: aim for at least 95% of valid export attempts in the
test set. - Workflow completion: aim for at least 50% of testers who
start a project to export one clip. - Unassisted usability: aim for at
least 80% of observed testers to complete the core workflow without
help. - Repeat use: measure the share of testers who start a second
project within 14 days; establish a baseline before setting a firm
go/no-go threshold. - Time saved: compare observed workflow time with
the user's current method; do not assume a target until a baseline
exists. - Quality: set numeric acceptance thresholds after labeling the
initial dataset.
