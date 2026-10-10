# ClipGen --- Overhaul Documentation Pack

**Purpose:** Product and engineering blueprint for a major ClipGen
overhaul, using a local-first development and processing strategy.

**Status:** Proposed blueprint. This is not a codebase audit. Current
stack, existing modules, actual performance, and current feature
completeness must be verified against the repository before
implementation.

## Documents

1.  `01-product-requirements.md` --- product vision, target problem,
    principles, scope, acceptance criteria.
2.  `02-local-first-architecture.md` --- system boundaries, modules,
    data model, processing pipeline, local-first strategy.
3.  `03-editor-experience.md` --- editor workflow, UX requirements,
    interaction behavior, render parity.
4.  `04-clipping-quality-and-evaluation.md` --- clip quality rubric,
    score calibration, dataset and metrics.
5.  `05-testing-and-quality-gates.md` --- test strategy, CI gates,
    reliability, security and regression.
6.  `06-90-day-roadmap.md` --- phased execution, milestones, validation
    gates and investment criteria.
7.  `07-decisions-and-open-questions.md` --- assumptions, decisions to
    defer, repository audit checklist.

## How to use this pack

-   Treat these documents as the **target specification**, not proof
    that every proposed feature already exists.
-   Audit the repository before choosing a migration strategy. Preserve
    useful code; do not rewrite a working module solely to match this
    document.
-   Create small implementation tasks from the roadmap. Each task should
    have a clear acceptance criterion and a test.
-   Use Claude for product reasoning, architecture review, and critique;
    use Codex for implementation, tests, and iterative fixes. Either
    tool can do either job---keep the handoff and review explicit.
-   Start local-first. Introduce paid cloud infrastructure only when
    measurements or real user needs justify it.

## Core product thesis

ClipGen helps a creator turn a long video into a set of editable
short-video candidates, then finish and export those clips without
needing a separate editor for common tasks.

AI should accelerate the first draft. The user remains in control of the
final edit. A high internal score is not a promise of virality.

## Non-goals for the first rebuild

-   Recreating all of CapCut.
-   Promising views, virality, or monetization.
-   Building a multi-user cloud SaaS before validating the local
    workflow.
-   Adding many AI models or integrations before the baseline pipeline
    is measurable.
-   Rewriting the whole stack before understanding the current
    repository.

## Suggested implementation order

1.  Repository audit and baseline measurements.
2.  Stabilize one end-to-end path: source video → transcript → clip
    candidates → edit → preview → export.
3.  Fix correctness and usability before adding breadth.
4.  Evaluate clip quality on a small, labeled test set.
5.  Run observed beta sessions.
6.  Decide which parts, if any, need cloud execution.
