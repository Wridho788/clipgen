# 07 --- Decisions and Open Questions

## 1. Current known direction

-   ClipGen converts long-form video, especially podcast/interview-style
    content, into short clips for vertical platforms.
-   User wants a major product overhaul, not just a repository-analysis
    feature.
-   The initial investment is the user's own time and effort, with
    minimal new spending.
-   Local-first development and processing are the initial strategy.
-   Claude and Codex subscriptions are available to assist development;
    they should not be assumed to cover production API usage.
-   The editor is currently perceived as weaker than competitors that
    let users manually adjust clips and captions.
-   Earlier published clips did not reach 1,000 views despite a high
    internal score; the score must therefore be evaluated rather than
    trusted as a view predictor.

## 2. Assumptions that must be tested

-   Users want a single workflow from long video to edited export.
-   The editor can remove enough friction to justify choosing ClipGen
    over an AI clipping tool plus a general editor.
-   The initial audience has a recurring enough need to return.
-   Local processing can handle representative videos on the user's
    actual machine.
-   The candidate ranking can be made useful with available
    transcript/media signals.
-   Users will provide source material they have rights to process and
    publish.
-   There is a viable paid offering at a price that covers variable
    costs and ongoing work.

None of these assumptions should be described as proven market evidence.

## 3. Repository audit checklist

Before implementation, record: - \[ \] Repository URL/branch/commit
being audited. - \[ \] Languages, framework, package manager, runtime
versions. - \[ \] App entry points and module boundaries. - \[ \]
Existing transcript engine and model. - \[ \] Current
candidate-generation and scoring logic. - \[ \] Current media
processing/rendering implementation. - \[ \] Current storage model and
project persistence behavior. - \[ \] Current editor controls and known
limitations. - \[ \] Current deployment/build method. - \[ \] Existing
tests, lint/type-check/build commands. - \[ \] External APIs,
credentials, and paid dependencies. - \[ \] Known bugs and reproducible
failure steps. - \[ \] Which parts can be retained, refactored,
replaced, or removed.

## 4. Decisions to make only after the audit

-   Whether to keep the current framework.
-   Whether ClipGen should remain browser-based, use a desktop wrapper,
    or use a local companion worker.
-   Which transcription engine/model is the best local trade-off.
-   Whether the existing scoring algorithm should be repaired or
    replaced.
-   Whether rendering stays in-process or moves to a worker.
-   Which database/storage mechanism is appropriate.
-   Which export presets can be reliably supported.
-   Whether cloud processing is needed at all for the first beta.

Do not select a technology because it is fashionable. Select it because
it fits the actual repository, hardware, user workflow, and measured
constraints.

## 5. Questions for product validation

Ask users about recent behavior, not hypothetical interest: - What
long-form content did you last repurpose? - How did you find moments
worth clipping? - Which step took the longest? - What tools did you use,
and where did you switch tools? - How often do you publish clips? - What
makes you reject a generated clip? - Which manual adjustments are
non-negotiable? - What happens when a tool exports a bad result? - Have
you paid for a tool that solves this problem? What did you stop using? -
Would you try a paid pilot for a specific workflow? What would need to
be true?

Avoid asking only "Would you use ClipGen?" or "Would you pay for this?"
without a concrete task or offer.

## 6. Claude/Codex working protocol

### Before implementation

-   Write the task, context, expected behavior, non-goals, and
    acceptance criteria.
-   Provide the relevant code paths and current tests.
-   Ask for a plan and risks before broad changes.

### During implementation

-   Prefer small, reviewable changes.
-   Require tests for bug fixes and important behavior.
-   Do not accept a large rewrite without an explanation of what it
    replaces and why.
-   Do not let an AI tool claim tests passed unless it actually ran them
    and provides the result.

### Review

-   Review changed files and diff.
-   Run the tests/build locally.
-   Check for secrets, unsafe shell invocation, destructive file
    operations, and accidental dependency additions.
-   Ask the other tool to critique the implementation when the change is
    high-risk, but treat the critique as a second opinion, not proof.

### Useful task template

**Context:**\
\[Relevant current behavior and code locations\]

**Problem:**\
\[Observed problem with reproduction steps\]

**Desired behavior:**\
\[Specific outcome\]

**Constraints:**\
\[Local-first, no paid service, preserve compatibility, etc.\]

**Acceptance criteria:**\
- \[ \] ... - \[ \] ...

**Tests required:**\
\[Unit/integration/manual regression\]

**Deliverable:**\
\[Files changed, test results, known limitations\]

## 7. Cost discipline

-   No new subscription or cloud spend until a measured need exists.
-   Keep a ledger of any external API use, storage, and compute.
-   Measure cost and processing time per source-video minute.
-   Do not expose personal API keys in browser code or commit them to
    Git.
-   Treat free tiers and subscription quotas as changeable; verify
    current provider terms before depending on them.
-   Introduce paid infrastructure only when it removes a measured
    bottleneck or supports validated demand.

## 8. Go / pivot / pause framework

### Continue

-   Users complete the workflow.
-   Some users return with another source.
-   The tool solves a recurring problem.
-   Quality and cost are measurable and improving.

### Pivot

-   Users want the problem solved but repeatedly reject the current
    workflow or audience focus.
-   A different stage (e.g. caption editing rather than candidate
    discovery) provides substantially more value.
-   One user cohort demonstrates materially stronger repeat behavior
    than others.

### Pause or narrow

-   Users do not complete the core workflow after usability issues are
    addressed.
-   No cohort shows recurring need.
-   Processing demands exceed available hardware and there is no viable
    low-cost path.
-   The product cannot differentiate enough to justify ongoing
    maintenance.

The purpose of these rules is not to force a decision at day 90. It is
to make the decision evidence-based.
