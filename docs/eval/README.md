# Clip-quality evaluation kit

Implements the labeling protocol of `../04-clipping-quality-and-evaluation.md`.
Everything stays local; labels and reports for private material should not
be committed (`docs/eval/*.csv` and `docs/eval/report*.md` are git-ignored).

## 1. Collect candidates

Process 10–20 representative sources you have rights to (different lengths,
speakers, audio quality, pace, topics). Do not pick only sources where
ClipGen already looks good. Review candidates in the editor as usual:
accept, reject **with a reason**, trim, correct captions. Those actions are
recorded automatically.

## 2. Export a labeling sheet

```powershell
python scripts/eval_report.py template --out docs/eval/labels-2026-10.csv
```

One row per candidate, with algorithm version, rank, range, and a transcript
excerpt. Sample both high- and low-ranked candidates.

## 3. Score with the rubric (1–5)

| Column | 1 | 3 | 5 |
|---|---|---|---|
| `standalone_clarity` | Needs the full episode to make sense | Understandable with effort | Fully understandable alone |
| `context_completeness` | Key setup missing | Minor gap | Setup and point both present |
| `opening_strength` | Starts mid-thought or with filler | Gets going after a few seconds | Question/claim/conflict in the first seconds |
| `boundary_quality` | Cuts a word or thought | Slightly early/late | Natural start and end |
| `value_interest` | Nothing for the audience | Mildly useful/entertaining | Clear insight, payoff, or surprise |
| `caption_accuracy` | Meaning changed by errors | Some errors, meaning intact | Correct |
| `visual_readability` | Subject cropped out / captions unreadable | Acceptable | Well framed, captions easy to read |
| `audio_quality` | Speech inaudible or clipped | Usable | Clear |
| `pacing` | Long dead air or rushed | Some slack | Tight without losing context |
| `policy_rights` | Not publishable / no rights | Needs a check | Clearly fine to publish |

Set `critical_failure` to `y` when a clip is unusable without substantial
correction (any dimension at 1 also counts as critical). Have a second
reviewer score a subset independently and compare.

## 4. Report

```powershell
python scripts/eval_report.py report --labels docs/eval/labels-2026-10.csv --out docs/eval/report-2026-10.md
```

The report combines in-app signals (acceptance rate per algorithm version,
rejection reasons, boundary and caption corrections, render failures) with
the rubric (usable share, critical failure rate, per-dimension weaknesses,
Spearman correlation between rank and reviewer score, false positives and
false negatives).

Decision rule (docs/06 Phase 3 gate): if the correlation is weak (< 0.3) or
false positives are common, keep presenting the rank only as an
experimental ordering and adjust `SIGNAL_WEIGHTS` in
`backend/app/services/candidates.py` — bumping the algorithm version — then
re-evaluate on sources **not** used for tuning.
