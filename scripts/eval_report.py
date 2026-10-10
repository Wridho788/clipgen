"""
Clip-quality evaluation tooling (docs/04).

Two subcommands, standard library only, reading the local SQLite database:

  template  Write a labeling CSV (one row per candidate) using the 10-dimension
            rubric from docs/04 §2. Reviewers fill in 1–5 scores.
  report    Build a Markdown report from in-app review data (accept/reject
            reasons, boundary corrections, caption corrections, render
            failures) and, optionally, the filled rubric CSV (score-vs-human
            calibration, false positives/negatives).

Examples:
  python scripts/eval_report.py template --out docs/eval/labels-2026-10.csv
  python scripts/eval_report.py report --labels docs/eval/labels-2026-10.csv --out docs/eval/report.md

The internal rank is evaluated as a *ranking* signal only. Nothing here
predicts views; see docs/04 §5.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "backend" / "storage" / "app.db"

RUBRIC = [
    "standalone_clarity",
    "context_completeness",
    "opening_strength",
    "boundary_quality",
    "value_interest",
    "caption_accuracy",
    "visual_readability",
    "audio_quality",
    "pacing",
    "policy_rights",
]
RETAINED = {"accepted", "edited", "exported"}
REASON_LABELS = {
    "context_missing": "Konteks kurang",
    "weak_moment": "Momen lemah",
    "bad_boundaries": "Batas awal/akhir buruk",
    "transcript_error": "Transkrip salah",
    "repeated_content": "Konten berulang",
    "poor_crop": "Crop/framing buruk",
    "other": "Lainnya",
}


def load_clips(db_path: Path) -> list[dict]:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT c.*, j.source_name, j.source_duration_seconds, j.transcript_json, j.processing_options
        FROM clips c JOIN jobs j ON j.id = c.job_id
        ORDER BY j.created_at, c.created_at
        """
    ).fetchall()
    connection.close()
    clips = []
    for row in rows:
        item = dict(row)
        item["analysis"] = _json(item.get("analysis_json"), {})
        item["edit"] = _json(item.get("edit_json"), None)
        clips.append(item)
    # ``position`` only exists after schema migration 2; legacy databases keep creation order.
    clips.sort(key=lambda item: (item["job_id"], item.get("position") is None, item.get("position") or 0))
    return clips


def write_template(clips: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["clip_id", "job_id", "source", "algorithm_version", "rank", "total", "start_s", "end_s",
             "transcript_excerpt", "reviewer", *RUBRIC, "critical_failure", "notes"]
        )
        for clip in clips:
            analysis = clip["analysis"]
            writer.writerow([
                clip["id"], clip["job_id"], clip.get("source_name") or "", clip.get("algorithm_version") or "",
                analysis.get("rank", ""), analysis.get("total", ""),
                f"{clip['start_time']:.2f}", f"{clip['end_time']:.2f}",
                _excerpt(clip), "", *[""] * len(RUBRIC), "", "",
            ])
    print(f"Wrote {len(clips)} rows to {out}")


def build_report(clips: list[dict], labels_path: Path | None) -> str:
    lines = [
        "# ClipGen clip-quality evaluation",
        "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M}. Rank is an internal ranking signal, not a view forecast.",
        "",
    ]
    by_algorithm: dict[str, list[dict]] = defaultdict(list)
    for clip in clips:
        by_algorithm[clip.get("algorithm_version") or "unknown"].append(clip)

    lines += ["## In-app review signals", "",
              "| Algorithm | Candidates | Reviewed | Retained | Rejected | Acceptance rate | Render failures |",
              "|---|---|---|---|---|---|---|"]
    for algorithm, items in sorted(by_algorithm.items()):
        reviewed = [c for c in items if (c.get("review_status") or "suggested") != "suggested"]
        retained = [c for c in reviewed if c["review_status"] in RETAINED]
        rejected = [c for c in reviewed if c["review_status"] == "rejected"]
        failures = [c for c in items if c.get("status") == "failed"]
        rate = f"{len(retained) / len(reviewed):.0%}" if reviewed else "n/a"
        lines.append(f"| {algorithm} | {len(items)} | {len(reviewed)} | {len(retained)} | {len(rejected)} | {rate} | {len(failures)} |")

    reasons = Counter(c.get("review_reason") for c in clips if c.get("review_status") == "rejected")
    lines += ["", "### Rejection reasons", ""]
    if reasons:
        lines += ["| Reason | Count |", "|---|---|"]
        lines += [f"| {REASON_LABELS.get(reason, reason)} | {count} |" for reason, count in reasons.most_common()]
    else:
        lines.append("No rejected candidates yet.")

    deltas = []
    for clip in clips:
        if clip.get("suggested_start_time") is None or clip.get("suggested_end_time") is None:
            continue
        deltas.append((
            abs(clip["start_time"] - clip["suggested_start_time"]),
            abs(clip["end_time"] - clip["suggested_end_time"]),
        ))
    lines += ["", "### Boundary corrections (user trim vs. suggestion)", ""]
    if deltas:
        corrected = [d for d in deltas if max(d) > 0.5]
        starts = sorted(d[0] for d in corrected) or [0.0]
        ends = sorted(d[1] for d in corrected) or [0.0]
        lines += [
            f"- Clips with a boundary moved by more than 0.5 s: **{len(corrected)} / {len(deltas)}** ({len(corrected) / len(deltas):.0%}).",
            f"- Among corrected clips, start shift median {statistics.median(starts):.2f} s (max {max(starts):.2f} s); "
            f"end shift median {statistics.median(ends):.2f} s (max {max(ends):.2f} s).",
        ]
    else:
        lines.append("No clips with recorded suggestions.")

    cue_total = cue_transcribed = cue_corrected = clips_with_corrections = 0
    for clip in clips:
        edit = clip.get("edit") or {}
        cues = (edit.get("captions") or {}).get("cues") or []
        transcribed = [cue for cue in cues if cue.get("original_text") is not None]
        corrected = [cue for cue in transcribed if cue.get("text") != cue.get("original_text")]
        cue_total += len(cues)
        cue_transcribed += len(transcribed)
        cue_corrected += len(corrected)
        clips_with_corrections += 1 if corrected else 0
    lines += ["", "### Caption correction burden", ""]
    if cue_transcribed:
        lines += [
            f"- Transcribed caption lines corrected by users: **{cue_corrected} / {cue_transcribed}** ({cue_corrected / cue_transcribed:.0%}).",
            f"- Clips needing at least one caption correction: {clips_with_corrections}.",
        ]
    else:
        lines.append("No transcribed caption cues recorded yet.")

    if labels_path:
        lines += ["", *calibration_section(clips, labels_path)]
    else:
        lines += ["", "## Human rubric calibration", "",
                  "No rubric labels supplied. Run `template`, have reviewers score candidates 1–5, then pass `--labels`."]
    return "\n".join(lines) + "\n"


def calibration_section(clips: list[dict], labels_path: Path) -> list[str]:
    by_id = {clip["id"]: clip for clip in clips}
    rows = []
    with labels_path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            scores = []
            for key in RUBRIC:
                try:
                    scores.append(float(row.get(key) or ""))
                except ValueError:
                    pass
            if not scores:
                continue
            clip = by_id.get(row["clip_id"])
            rank = _float(row.get("rank")) or _float((clip or {}).get("analysis", {}).get("rank"))
            total = _float(row.get("total")) or _float((clip or {}).get("analysis", {}).get("total"))
            critical = (row.get("critical_failure") or "").strip().lower() in {"y", "yes", "ya", "1", "true"}
            minimum = min(scores)
            rows.append({
                "clip_id": row["clip_id"],
                "reviewer": row.get("reviewer") or "",
                "mean": statistics.mean(scores),
                "min": minimum,
                "critical": critical or minimum <= 1,
                "rank": rank,
                "total": total,
                "dims": {key: _float(row.get(key)) for key in RUBRIC},
            })
    out = ["## Human rubric calibration", ""]
    if not rows:
        return out + ["Label file contains no scored rows."]
    usable = [row for row in rows if not row["critical"] and row["mean"] >= 3]
    out += [
        f"- Scored candidates: {len(rows)} (reviewers: {len({row['reviewer'] for row in rows if row['reviewer']}) or 'n/a'}).",
        f"- Usable starting points (mean ≥ 3, no critical failure): **{len(usable)} / {len(rows)}** ({len(usable) / len(rows):.0%}).",
        f"- Critical failure rate: {sum(row['critical'] for row in rows) / len(rows):.0%}.",
        "",
        "| Dimension | Mean | Share ≤ 2 |", "|---|---|---|",
    ]
    for key in RUBRIC:
        values = [row["dims"][key] for row in rows if row["dims"][key] is not None]
        if values:
            out.append(f"| {key} | {statistics.mean(values):.2f} | {sum(v <= 2 for v in values) / len(values):.0%} |")
    ranked = [row for row in rows if row["rank"] and row["total"]]
    out += ["", "### Does the rank agree with reviewers?", ""]
    if len(ranked) >= 4:
        # Normalised rank: 1.0 = top candidate of its job.
        relative = [1 - (row["rank"] - 1) / max(1, row["total"] - 1) if row["total"] > 1 else 1.0 for row in ranked]
        rho = spearman(relative, [row["mean"] for row in ranked])
        out.append(f"- Spearman correlation between relative rank and mean rubric score: **{rho:.2f}** (n={len(ranked)}).")
        out.append("- Interpretation: ≥ 0.3 suggests a useful ranking signal; near 0 means the rank should be demoted to an experimental heuristic.")
        false_positive = [row for row in ranked if row["rank"] == 1 and (row["critical"] or row["mean"] < 2.5)]
        false_negative = [row for row in ranked if row["rank"] == row["total"] and row["total"] > 1 and row["mean"] >= 4]
        out.append(f"- False positives (rank #1 but weak/critical): {len(false_positive)} — {', '.join(r['clip_id'][:8] for r in false_positive) or 'none'}.")
        out.append(f"- False negatives (lowest rank but scored ≥ 4): {len(false_negative)} — {', '.join(r['clip_id'][:8] for r in false_negative) or 'none'}.")
    else:
        out.append("Need at least 4 ranked, scored candidates to estimate agreement.")
    return out


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda index: values[index])
        result = [0.0] * len(values)
        position = 0
        while position < len(order):
            end = position
            while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
                end += 1
            average = (position + end) / 2 + 1
            for index in order[position:end + 1]:
                result[index] = average
            position = end + 1
        return result

    rx, ry = ranks(xs), ranks(ys)
    mean_x, mean_y = statistics.mean(rx), statistics.mean(ry)
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry))
    denominator = (sum((a - mean_x) ** 2 for a in rx) * sum((b - mean_y) ** 2 for b in ry)) ** 0.5
    return numerator / denominator if denominator else 0.0


def _excerpt(clip: dict, limit: int = 220) -> str:
    segments = _json(clip.get("transcript_json"), [])
    words = [
        str(segment.get("text", "")).strip()
        for segment in segments if isinstance(segment, dict)
        and float(segment.get("start", 0)) < clip["end_time"] and float(segment.get("end", 0)) > clip["start_time"]
    ]
    text = " ".join(words)
    return text[:limit] + ("…" if len(text) > limit else "")


def _json(raw, default):
    try:
        value = json.loads(raw) if raw else default
    except (TypeError, json.JSONDecodeError):
        return default
    return value if value is not None else default


def _float(value) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)
    template = sub.add_parser("template")
    template.add_argument("--out", type=Path, required=True)
    report = sub.add_parser("report")
    report.add_argument("--labels", type=Path)
    report.add_argument("--out", type=Path)
    args = parser.parse_args()

    clips = load_clips(args.db)
    if args.command == "template":
        write_template(clips, args.out)
        return 0
    text = build_report(clips, args.labels)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
