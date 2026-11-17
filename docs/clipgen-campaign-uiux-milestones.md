# ClipGen — Campaign Workflow & UI/UX Milestones

**Status:** Draft product plan; not yet audited against the actual repository.

## 1. Product direction

ClipGen should evolve from a general-purpose video clipper into a **campaign-driven clipping workspace**. Users copy campaign details from a third-party Clipper Campaign website, paste them into ClipGen, review the extracted rules, select a source video, generate relevant clip candidates, edit, validate, and export.

### Core principles
- Campaign brief and rules influence candidate discovery, ranking, validation, and editing recommendations.
- Start with copy-paste import; do not require external platform APIs for the MVP.
- Never invent missing campaign rules. Mark missing or ambiguous fields as `unknown` / `needs review`.
- Keep **campaign compliance** separate from **editorial quality**. Passing a campaign's rules does not guarantee views, virality, or rewards.
- Save a versioned campaign configuration snapshot for every clipping job.
- Preserve a local-first approach where practical and control external API costs.

## 2. Primary user flow

1. Open the external campaign website.
2. Copy the campaign brief and all available details.
3. Paste the text into **Import Campaign**.
4. Parse the text into structured fields.
5. Review and correct extracted fields; confirm hard constraints and soft preferences.
6. Save the campaign.
7. Upload/select a source video.
8. Transcribe and analyze the source.
9. Discover and rank candidate moments based on campaign relevance and editorial quality.
10. Check applicable campaign constraints.
11. Review candidate clips and their selection rationale.
12. Edit trim, subtitles, framing, hook, and caption.
13. Run final validation and export.

## 3. Campaign types

### Reward campaign
Possible fields: campaign name, organizer, brief, reward terms, approved source creators/videos, allowed platforms, minimum/maximum duration, required hashtags/mentions/CTA, prohibited content, dates, submission requirements, and evidence requirements.

**Important:** reward terms, content permissions, and eligibility must not be presented as verified unless the source information supports that claim.

### Custom campaign
User-defined name, objective, brief, audience, platform, duration, candidate count, hook style, tone, subtitle/caption preferences, CTA, hashtags, and topics or claims to avoid.

### Hard constraints vs. soft preferences
- **Hard constraints:** mandatory, testable rules such as duration limits or allowed sources.
- **Soft preferences:** desired qualities such as hook style, tone, pacing, and target audience.

Show at least two distinct evaluations:
- `Campaign compliance`: pass / fail / needs review / unknown.
- `Editorial quality`: an explainable evaluation of relevance, context, and editing potential.

Do not combine them into one unexplained “viral score”.

## 4. Suggested data model

Adapt these concepts to the existing repository rather than implementing blindly.

### `Campaign`
`id`, `name`, `type` (`reward` / `custom`), `source` (`manual_import` / `user_created`), `source_name`, optional `source_url`, `status`, timestamps.

### `CampaignConfiguration`
`campaign_id`, `version`, `raw_source_text`, `objective`, `brief`, `target_audience`, `platforms`, `hard_constraints`, `soft_preferences`, optional `reward_details`, `unresolved_items`, `user_confirmed_at`.

### `SourceVideo`
`id`, `project_id`, source/file reference, duration, metadata, transcription status, analysis status.

### `ClippingJob`
`id`, `campaign_id`, `campaign_configuration_version`, `source_video_id`, status, pipeline settings, creation time.

### `ClipCandidate`
`id`, `clipping_job_id`, start/end time, transcript excerpt, campaign relevance, editorial evaluation, compliance status/findings, selection rationale.

### `ClipProject`
`id`, `candidate_id`, edit state, caption settings, framing settings, export settings/status.

## 5. UI/UX direction

### References
- [ClipPilot — AI Video Editor Dashboard (Dribbble)](https://dribbble.com/shots/27106290-ClipPilot-AI-Video-Editor-Dashboard)
- [OpusClip](https://www.opus.pro/) — source video to candidate clips.
- [Riverside Video Editor](https://riverside.com/video-editor) — editor and export flow.
- [Descript](https://www.descript.com/) — transcript-based editing.
- [Dribbble: AI Video Editor](https://dribbble.com/search/ai-video-editor)
- [Dribbble: Video Editor Dashboard](https://dribbble.com/search/video-editor-dashboard)

Use references for patterns, not as proof of usability or a specification to copy.

### Visual direction
- Dark creative workspace, with video content as the focus.
- Starting tokens: background `#111318`, elevated panel `#20232B`, primary accent `#8B5CF6`, secondary accent `#22D3EE`.
- Consider Inter or Geist; keep typography and spacing consistent.
- Avoid excessive glow, gradients, or glassmorphism.
- Ensure contrast, readable text, clear focus/active states, and responsive layouts.
- Desktop-first for the editor; responsive layouts for dashboard, import, and candidate review.

### A. Dashboard / Projects
- `New Project` primary action.
- Recent projects and processing status.
- Recently used campaigns.
- Export history.
- Useful empty state for first-time users.

### B. Import Campaign
- Large paste-text area.
- `Analyze Campaign` action and loading/error states.
- Extracted fields grouped by topic.
- `Found`, `Needs review`, and `Not provided` indicators.
- Editable results and `Confirm & Save Campaign`.
- Do not start clipping before the user confirms important or ambiguous rules.

### C. Campaign Detail / Rules
- Brief and objective.
- Hard constraints and soft preferences.
- Reward and submission details if present.
- Raw imported text and source details.
- Unverified fields, configuration version, and change history.

### D. Generated Clips
- Vertical 9:16 previews.
- Duration and source time range.
- Transcript excerpt or moment summary.
- Rationale for why each candidate was selected.
- Compliance status separate from editorial evaluation.
- Contextual actions such as `Edit`, `Regenerate`, `Reject`, and `Export`.

### E. Clip Workspace / Editor
- **Left:** media library, source video, candidates, assets.
- **Center:** large video preview.
- **Bottom:** timeline and video/subtitle/audio tracks when supported.
- **Right:** properties inspector and Campaign Assistant.
- Precise trim, seek, preview, subtitle styling/timing, 9:16 framing, caption/hook editing.
- Undo/redo for important changes.
- Preview AI changes before applying them.
- Clear save state and export status.

### F. Campaign Assistant
Adapt the AI Enhance panel idea from ClipPilot to campaign-aware assistance:
- Campaign requirements and compliance findings.
- Hook/pacing recommendations with source time ranges.
- Subtitle safe-area checks.
- Explanation plus `Preview`, `Apply`, `Dismiss`, and `Undo` actions where applicable.
- Never silently modify the edit.
- Never use unexplained percentages or imply guaranteed performance.

### Interaction and state requirements
Design loading, empty, success, partial success, and error states. Cover parsing failures, conflicting rules, failed transcription, no candidates, long-running jobs, cancellation, export failures, unsaved changes, and insufficient disk space. Use confirmations for destructive actions and keyboard accessibility where practical.

## 6. Milestones

These milestones are ordered by dependency. Estimate calendar duration only after the repository audit.

### M0 — Repository audit and baseline
**Work**
- Audit stack, folders, entry points, state, persistence, upload, transcription, candidate generation, editor, and export.
- Run available tests, lint, typecheck, and build.
- Identify working features, placeholders, bugs, dependencies, API usage, and cost risks.
- Record a reproducible baseline for representative local videos.

**Deliverables:** `REPOSITORY_AUDIT.md`, architecture map, risk list, baseline results.

**Acceptance:** no major refactor before baseline; primary pipeline and failure points are understood.

### M1 — Product flow and UX foundation
**Work**
- Finalize Import → Review → Select Video → Generate → Review Clips → Edit → Validate → Export.
- Wireframe Dashboard, Import Campaign, Campaign Detail, Generated Clips, and Clip Workspace.
- Define navigation, design tokens, components, responsive behavior, and UI states.
- Prototype the campaign import flow.

**Deliverables:** user flow, wireframes, design tokens, component/interaction inventory.

**Acceptance:** next steps are clear; editor preserves adequate space for preview and timeline.

### M2 — Campaign import and normalization
**Work**
- Implement raw text paste.
- Parse predictable fields with deterministic rules first.
- If an LLM is used, validate its output against a schema.
- Extract campaign fields; separate constraints from preferences.
- Flag missing, ambiguous, or conflicting data.
- Allow review, edits, confirmation, and save.
- Handle empty, long, malformed, and partially structured input.

**Acceptance**
- Imported text is editable and can be saved.
- Missing fields are not guessed.
- Important ambiguous rules are flagged.
- Saved campaign can be reopened.

### M3 — Persistence and versioning
**Work**
- Persist campaigns and configuration versions in the existing appropriate storage layer.
- Save raw source text.
- Link each job to the exact configuration version used.
- Support edit and duplicate; consider archive/re-import.
- Define behavior when a campaign is updated after a job starts.

**Acceptance**
- Campaign survives app restart.
- Old jobs retain their original configuration snapshot.
- Campaign updates do not silently change old evaluations.

### M4 — Campaign-aware clipping pipeline
**Work**
- Pass campaign configuration into analysis.
- Use brief/topics for candidate discovery and ranking.
- Rank using relevance, context, and editorial potential.
- Apply deterministic checks for testable hard constraints.
- Save candidate rationale and compliance findings.

**Acceptance**
- Different campaigns can produce different rankings for the same source.
- Candidates link to a campaign configuration version.
- No claims that internal scores guarantee views or rewards.

### M5 — Generated Clips and Campaign Assistant
**Work**
- Build candidate cards/list with preview, duration, source range, and rationale.
- Separate compliance from editorial evaluation.
- Add simple sorting/filtering if candidate volume warrants it.
- Add recommendations with preview/apply/dismiss/undo.
- Design no-candidate, partial-result, and job-failure states.

**Acceptance:** users can compare candidates without opening each editor; AI changes are never silent.

### M6 — Editor improvement
**Work**
- Audit the current editor before choosing a library or rewriting it.
- Prioritize precise trim, seek, preview synchronization, subtitle editing, and 9:16 framing.
- Add timeline tracks where supported.
- Persist edit state and add undo/redo for key operations.
- Integrate campaign context into the inspector.
- Clarify autosave and unsaved-change behavior.

**Acceptance**
- Trim is precise and reflected in preview.
- Subtitle/framing settings persist.
- Unsaved changes are visible.
- AI recommendations can be previewed before applying.

### M7 — Export and final validation
**Work**
- Validate aspect ratio, resolution, duration, and output format.
- Run applicable campaign checks before export.
- Show warnings for rules that cannot be automatically verified.
- Handle cancellation, failure, and incomplete output.
- Keep output associated with the project and campaign.

**Acceptance**
- Exported files are playable and match the chosen output settings.
- Failed exports are never shown as successful.
- Unknown rules remain warnings, not passes.

### M8 — Reliability, usability, and beta
**Work**
- Test import, schema validation, persistence/versioning, ranking, compliance, editor state, and export.
- Test complete, sparse, ambiguous, contradictory, and unstructured campaign text.
- Test representative videos and local resource usage.
- Run end-to-end usability sessions.
- Prioritize fixes by user impact.

**Acceptance**
- Main workflow completes without undocumented workarounds.
- Errors provide recovery steps or clear explanations.
- Known limitations are documented.
- No unsupported claims about eligibility, virality, or reward.

## 7. Improvement priority

### P0 — MVP
- Campaign copy-paste import and structured parsing.
- Review and confirmation.
- Persistence and per-job configuration snapshots.
- Campaign-aware candidate ranking.
- Separate compliance and editorial evaluation.
- Generated Clips review.
- Reliable core editing and export.
- Error handling and automated tests for key paths.

### P1 — After MVP is stable
- Campaign templates and duplicate.
- Configuration history.
- Candidate filtering/sorting.
- AI recommendations with preview/apply/undo.
- Improved subtitle/framing controls.
- Expanded pre-export checklist.
- Better long-running job and cancellation UX.

### P2 — Validate demand before building
- Automatic sync from external campaign platforms.
- Submission/reward integrations.
- Cross-platform performance analytics.
- Multi-user collaboration.
- Cloud sync/storage.
- Predictive performance features.

## 8. Testing and quality gates

### Import
- Empty and very long text.
- Missing, repeated, conflicting, or ambiguous fields.
- Partial parsing.
- User corrections before save.
- Irrelevant instructions inside pasted content do not override the campaign schema.

### Persistence
- App restart.
- Edit/duplicate campaign.
- Configuration update.
- Old jobs retain old versions.
- Migration when the schema changes.

### Clipping
- Same video under different campaigns.
- No matching candidates.
- Partial compliance.
- Duration outside constraints.
- Candidate rationale is present.
- Scores are not described as guaranteed performance.

### Editor/export
- Trims at beginning, middle, and end.
- Long/short subtitles.
- Framing changes.
- Undo/redo and reopen.
- Export failure/cancellation/disk-space errors.
- Output playback and duration validation.

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Campaign formats vary | Preserve raw text; allow manual review and unknown fields |
| AI invents rules | Schema validation, explicit unknown state, user confirmation |
| Campaign changes later | Versioned configurations and job snapshots |
| Score mistaken for virality | Explain metrics and separate compliance from editorial quality |
| Video rights are unclear | Do not assert permission without evidence; surface source rules |
| Editor scope expands | Audit existing editor; prioritize trim, preview, subtitles, framing, export |
| API costs grow | Local-first defaults; optional external model integration |
| UI looks good but is hard to use | Test actual tasks; treat Dribbble as inspiration, not usability evidence |

## 10. Definition of Done

A milestone is complete when:
- It is implemented in the actual repository, not only represented by a mockup.
- Acceptance criteria pass.
- Loading, empty, success, and error states are handled.
- Relevant tests run and results are recorded.
- Campaign data and statuses are not fabricated.
- Documentation is updated.
- The workflow can be run locally using documented steps.
- Remaining limitations are tracked.

## 11. Next actions

1. Audit the current ClipGen repository.
2. Map each feature to `existing`, `partial`, `missing`, or `blocked`.
3. Finalize the UX flow and wireframes.
4. Implement M2 campaign import before adding external integrations.
5. Use Claude for product/UX critique, edge cases, and architecture review.
6. Use Codex for repository audit, implementation, tests, and regression fixes.
7. Use cross-tool review for major or risky changes, not every small bug.

**Product principle:** build a dependable workflow first — import campaign → confirm rules → select video → generate candidates → edit → validate → export. Add automation and external integrations only after the core flow proves useful.
