"""
Real end-to-end check against a running ClipGen stack (docs/05 §2, §9).

Uses only the Python standard library plus host ffprobe/ffmpeg. Exercises the
full workflow with real Whisper transcription, real FFmpeg rendering and (when
available) real Ollama metadata:

  import → transcript → candidates → edit (trim, caption text/style, framing)
  → autosave conflict → validated re-render → download + ffprobe → caption
  burn-in pixel check → backend restart → persistence → review/duplicate →
  source immutability → log hygiene, plus the invalid-input paths.

Usage (from the repository root, stack running via docker compose):
    python scripts/e2e_real.py [--api http://localhost:8000] [--no-restart]

Writes a JSON report to release-artifacts/e2e/. Exit code 0 only if every
check passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "backend" / "tests" / "fixtures" / "media"
STORAGE = ROOT / "backend" / "storage"


class Check:
    def __init__(self) -> None:
        self.results: list[dict] = []

    def __call__(self, name: str, ok: bool, detail: object = "") -> bool:
        self.results.append({"check": name, "ok": bool(ok), "detail": detail})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{f' — {detail}' if detail not in ('', None) else ''}", flush=True)
        return bool(ok)

    @property
    def failed(self) -> list[dict]:
        return [item for item in self.results if not item["ok"]]


def request(api: str, method: str, path: str, *, json_body=None, data: bytes | None = None,
            headers: dict | None = None, timeout: int = 120):
    body = data
    all_headers = dict(headers or {})
    if json_body is not None:
        body = json.dumps(json_body).encode()
        all_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(api + path, data=body, method=method, headers=all_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            status = response.status
            response_headers = dict(response.headers)
    except urllib.error.HTTPError as error:
        raw = error.read()
        status = error.code
        response_headers = dict(error.headers)
    content_type = response_headers.get("content-type", response_headers.get("Content-Type", ""))
    payload = json.loads(raw) if "json" in content_type and raw else raw
    return status, payload


def upload(api: str, file_path: Path, fields: dict[str, str]):
    boundary = uuid.uuid4().hex
    parts = []
    for key, value in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file_path.name}\"\r\n"
        f"Content-Type: {mime}\r\n\r\n".encode() + file_path.read_bytes() + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return request(api, "POST", "/api/videos/upload", data=b"".join(parts),
                   headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, timeout=600)


def wait_for(predicate, timeout_s: float, interval_s: float = 3.0, label: str = ""):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval_s)
    raise TimeoutError(f"Timed out waiting for {label}")


def ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    video = next(stream for stream in data["streams"] if stream["codec_type"] == "video")
    return {
        "width": video["width"], "height": video["height"],
        "duration": float(data["format"]["duration"]),
        "audio": any(stream["codec_type"] == "audio" for stream in data["streams"]),
    }


def band_luma(path: Path, at_s: float, center_fraction: float, height_fraction: float = 0.04) -> list[int]:
    """Gray pixels of a horizontal band (central half) of one frame."""
    info = ffprobe(path)
    width, height = info["width"], info["height"]
    band_h = max(4, int(height * height_fraction)) // 2 * 2
    y = max(0, int(height * center_fraction) - band_h // 2)
    crop = f"crop={width // 2}:{band_h}:{width // 4}:{y}"
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{at_s:.3f}", "-i", str(path), "-frames:v", "1", "-vf", crop,
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True,
    ).stdout
    return list(raw)


def mean_abs_diff(a: list[int], b: list[int]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / max(1, min(len(a), len(b)))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    # Windows consoles default to cp1252; keep check names readable everywhere.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=os.environ.get("CLIPGEN_API", "http://localhost:8000"))
    parser.add_argument("--no-restart", action="store_true", help="skip the backend restart persistence check")
    parser.add_argument("--container", default="clipgen-backend")
    parser.add_argument("--job-timeout", type=int, default=3600)
    args = parser.parse_args()
    api = args.api.rstrip("/")
    check = Check()
    timings: dict[str, float] = {}
    work = ROOT / "release-artifacts" / "e2e"
    work.mkdir(parents=True, exist_ok=True)
    started = time.time()

    print("== Health")
    status, health = request(api, "GET", "/health/ready")
    check("backend ready", status == 200 and health.get("database"), health)

    print("== Invalid input is rejected with stable codes")
    status, body = upload(api, FIXTURES / "corrupt.mp4", {"generate_metadata": "true"})
    check("corrupt file → 400 SOURCE_CORRUPT", status == 400 and body.get("code") == "SOURCE_CORRUPT", body)
    status, body = upload(api, FIXTURES / "no_audio.mp4", {"generate_metadata": "true"})
    check("no-audio file with metadata → 400 AUDIO_MISSING", status == 400 and body.get("code") == "AUDIO_MISSING", body)
    bogus = work / "notes.txt"
    bogus.write_text("not a video")
    status, body = upload(api, bogus, {})
    check("unsupported extension → 400 SOURCE_UNSUPPORTED", status == 400 and body.get("code") == "SOURCE_UNSUPPORTED", body)

    print("== Import + analysis (real Whisper, FFmpeg, Ollama)")
    fixture = FIXTURES / "speech_landscape.mp4"
    t0 = time.time()
    status, created = upload(api, fixture, {
        "output_preset": "tiktok", "visual_style": "crop", "metadata_language": "en",
        "clip_count": "2", "min_clip_seconds": "15", "max_clip_seconds": "30",
        "burn_captions": "true", "generate_metadata": "true",
    })
    if not check("upload accepted", status == 200 and created.get("job_id"), created):
        return finish(check, timings, work, started)
    job_id = created["job_id"]
    source_copy = STORAGE / "uploads" / f"{job_id}.mp4"
    check("source stored byte-identical to the upload", source_copy.exists() and sha256(source_copy) == sha256(fixture))

    def job_terminal():
        _, job = request(api, "GET", f"/api/jobs/{job_id}")
        return job if job.get("status") in {"done", "failed", "cancelled"} else None

    job = wait_for(job_terminal, args.job_timeout, 5, "job completion")
    timings["job_total_s"] = round(time.time() - t0, 1)
    timings.update({f"stage_{key}_s": value for key, value in (job.get("stage_metrics") or {}).items()})
    check("job done", job["status"] == "done", job.get("error_message"))
    transcript_summary = (job.get("automatic_summary") or {}).get("transcript", {})
    check("transcript normalized and summarized", transcript_summary.get("segments", 0) > 5, transcript_summary)

    status, clips = request(api, "GET", f"/api/clips/job/{job_id}")
    check("two candidate clips", status == 200 and len(clips) == 2, len(clips) if isinstance(clips, list) else clips)
    for index, clip in enumerate(clips, start=1):
        candidate = clip.get("candidate") or {}
        report = clip.get("render_report") or {}
        validation = report.get("validation") or {}
        check(f"clip {index}: ready + validated 1080x1920", clip["status"] == "ready" and validation.get("ok")
              and (validation.get("width"), validation.get("height")) == (1080, 1920), validation.get("problems"))
        check(f"clip {index}: transcript-boundary candidate with explanation",
              candidate.get("algorithm_version") == "transcript-boundary-v1" and candidate.get("explanation"), candidate.get("explanation"))
        check(f"clip {index}: no raw score/percentage exposed", "score" not in candidate and "bukan prediksi" in candidate.get("score_meaning", ""))
        check(f"clip {index}: ends on a complete sentence", candidate.get("signals", {}).get("complete_ending") == 1.0, candidate.get("signals"))
        check(f"clip {index}: captions prepared from transcript", clip["edit"]["captions"]["enabled"] and len(clip["edit"]["captions"]["cues"]) > 0)
        check(f"clip {index}: suggestion recorded", clip["suggested_start_time"] == clip["start_time"])
        check(f"clip {index}: metadata generated", bool(clip.get("title")), clip.get("title"))

    clip = clips[0]
    clip_id = clip["id"]
    download = work / f"{clip_id}-r1.mp4"
    status, data = request(api, "GET", f"/api/clips/{clip_id}/file", timeout=300)
    download.write_bytes(data if isinstance(data, bytes) else b"")
    probed = ffprobe(download)
    expected = (clip["edit"]["trim_end_ms"] - clip["edit"]["trim_start_ms"]) / 1000
    check("initial export probes as 1080x1920 with audio", (probed["width"], probed["height"], probed["audio"]) == (1080, 1920, True), probed)
    check("initial export duration matches trim (±0.35s)", abs(probed["duration"] - expected) <= 0.35, f"{probed['duration']:.3f} vs {expected:.3f}")

    print("== Edit: trim, caption text + style, framing")
    edit = clip["edit"]
    edit["trim_start_ms"] += 1000
    visible = [cue for cue in edit["captions"]["cues"] if edit["trim_start_ms"] + 500 <= cue["start_ms"] < edit["trim_end_ms"] - 1500]
    target_cue = visible[0]
    target_cue["text"] = "EDITED CAPTION E2E"
    edit["captions"]["style"].update({"background": "box", "text_color": "#ffe14d", "position_y": 0.7, "font_size": 72})
    edit["framing"]["focus_x"] = 0.3
    status, saved = request(api, "PUT", f"/api/clips/{clip_id}/edit", json_body={"base_revision": clip["edit_revision"], "edit": edit})
    check("autosave accepted", status == 200 and saved["edit_revision"] == clip["edit_revision"] + 1, saved.get("detail") if isinstance(saved, dict) else saved)
    check("render marked stale after edit", saved.get("render_stale") is True)
    check("review status → edited", saved.get("review_status") == "edited")
    check("colour normalized server-side", saved["edit"]["captions"]["style"]["text_color"] == "#FFE14D")
    status, conflict = request(api, "PUT", f"/api/clips/{clip_id}/edit", json_body={"base_revision": clip["edit_revision"], "edit": edit})
    check("stale autosave rejected with EDIT_CONFLICT", status == 409 and conflict.get("code") == "EDIT_CONFLICT", conflict)

    print("== Validated re-render of the saved edit")
    t1 = time.time()
    status, queued = request(api, "POST", f"/api/clips/{clip_id}/render")
    check("render queued", status == 202 and queued["status"] == "processing", queued.get("detail") if isinstance(queued, dict) else queued)

    def rendered():
        _, current = request(api, "GET", f"/api/clips/{clip_id}")
        return current if current["status"] != "processing" else None

    current = wait_for(rendered, 900, 3, "re-render")
    timings["rerender_s"] = round(time.time() - t1, 1)
    check("re-render ready at saved revision", current["status"] == "ready" and current["rendered_revision"] == saved["edit_revision"]
          and not current["render_stale"], current.get("render_error_message"))
    check("re-render passed validation", (current.get("render_report") or {}).get("validation", {}).get("ok"), (current.get("render_report") or {}).get("validation", {}).get("problems"))
    download2 = work / f"{clip_id}-r{current['rendered_revision']}.mp4"
    status, data = request(api, "GET", f"/api/clips/{clip_id}/file", timeout=300)
    download2.write_bytes(data)
    probed2 = ffprobe(download2)
    expected2 = (edit["trim_end_ms"] - edit["trim_start_ms"]) / 1000
    check("edited export duration follows new trim", abs(probed2["duration"] - expected2) <= 0.35, f"{probed2['duration']:.3f} vs {expected2:.3f}")
    check("old file replaced (not left behind)", not Path(clip["file_path"].replace("/app/storage", str(STORAGE))).exists())

    print("== Caption burn-in matches the saved style/position")
    at = (target_cue["start_ms"] + min(target_cue["end_ms"], edit["trim_end_ms"])) / 2000 - edit["trim_start_ms"] / 1000
    with_caption = band_luma(download2, at, 0.7)
    no_caption_edit = json.loads(json.dumps(current["edit"]))
    no_caption_edit["captions"]["enabled"] = False
    status, saved_off = request(api, "PUT", f"/api/clips/{clip_id}/edit", json_body={"base_revision": current["edit_revision"], "edit": no_caption_edit})
    request(api, "POST", f"/api/clips/{clip_id}/render")
    current_off = wait_for(rendered, 900, 3, "caption-off render")
    download3 = work / f"{clip_id}-nocaption.mp4"
    _, data = request(api, "GET", f"/api/clips/{clip_id}/file", timeout=300)
    download3.write_bytes(data)
    without_caption = band_luma(download3, at, 0.7)
    control_with = band_luma(download2, at, 0.25)
    control_without = band_luma(download3, at, 0.25)
    caption_diff = mean_abs_diff(with_caption, without_caption)
    control_diff = mean_abs_diff(control_with, control_without)
    check("caption visible at saved position (band differs)", caption_diff > 20, f"diff={caption_diff:.1f}")
    check("frame elsewhere unchanged", control_diff < 4, f"diff={control_diff:.1f}")
    check("caption toggle respected (0 captions rendered)", (current_off.get("render_report") or {}).get("captions_rendered") == 0)
    # Restore captions for the persistence checks.
    restore = json.loads(json.dumps(current_off["edit"]))
    restore["captions"]["enabled"] = True
    status, restored = request(api, "PUT", f"/api/clips/{clip_id}/edit", json_body={"base_revision": current_off["edit_revision"], "edit": restore})
    check("captions re-enabled", status == 200)

    if not args.no_restart:
        print("== Restart backend and reopen")
        subprocess.run(["docker", "restart", args.container], check=True, capture_output=True)
        wait_for(lambda: _alive(api) or None, 180, 3, "backend restart")
    status, reopened = request(api, "GET", f"/api/clips/{clip_id}")
    cue_texts = [cue["text"] for cue in reopened["edit"]["captions"]["cues"]]
    check("edits persist after reopen/restart", "EDITED CAPTION E2E" in cue_texts
          and reopened["edit"]["captions"]["style"]["background"] == "box"
          and reopened["edit"]["trim_start_ms"] == edit["trim_start_ms"]
          and reopened["edit"]["framing"]["focus_x"] == 0.3)
    check("unrendered change still flagged stale after reopen", reopened["render_stale"] is True)

    print("== Review, order, duplicate")
    other = clips[1]["id"]
    status, body = request(api, "POST", f"/api/clips/{other}/review", json_body={"status": "rejected"})
    check("reject without reason refused", status == 422 and body.get("code") == "EDIT_INVALID")
    status, body = request(api, "POST", f"/api/clips/{other}/review", json_body={"status": "rejected", "reason": "weak_moment"})
    check("reject with reason", status == 200 and body["review_status"] == "rejected")
    status, body = request(api, "POST", f"/api/clips/{clip_id}/review", json_body={"status": "accepted"})
    check("accept", status == 200 and body["review_status"] == "accepted")
    status, ordered = request(api, "POST", f"/api/clips/job/{job_id}/order", json_body={"clip_ids": [other, clip_id]})
    check("reorder", status == 200 and [item["id"] for item in ordered] == [other, clip_id])
    status, copy = request(api, "POST", f"/api/clips/{clip_id}/duplicate")
    check("duplicate", status == 201 and copy["edit"]["trim_start_ms"] == edit["trim_start_ms"])
    status, archive = request(api, "GET", f"/api/clips/job/{job_id}/archive", timeout=300)
    import io
    import zipfile
    names = zipfile.ZipFile(io.BytesIO(archive)).namelist() if status == 200 else []
    check("ZIP export excludes rejected candidates", status == 200 and len(names) == 2, names)

    print("== Integrity and hygiene")
    check("source still byte-identical after all edits", sha256(source_copy) == sha256(fixture))
    log_file = ROOT / "backend" / "logs" / "clipgen.log"
    log_text = log_file.read_text(encoding="utf-8", errors="ignore")[-2_000_000:] if log_file.exists() else ""
    leaked = [marker for marker in ("Authorization: Bearer", "password=", "auth_secret_key") if marker in log_text]
    check("logs contain no credential markers", not leaked, leaked)
    temp_dir = STORAGE / "temp"
    partials = [path.name for path in temp_dir.glob("*.partial.mp4")] if temp_dir.exists() else []
    check("no partial render files left in temp", not partials, partials)

    timings["total_s"] = round(time.time() - started, 1)
    return finish(check, timings, work, started, job_id=job_id)


def _alive(api: str) -> bool:
    try:
        return request(api, "GET", "/health/live", timeout=5)[0] == 200
    except Exception:
        return False


def finish(check: Check, timings: dict, work: Path, started: float, job_id: str | None = None) -> int:
    report = {
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "job_id": job_id,
        "passed": len(check.results) - len(check.failed),
        "failed": len(check.failed),
        "timings": timings,
        "results": check.results,
    }
    path = work / f"e2e-real-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\n{report['passed']} passed, {report['failed']} failed — report: {path}")
    print("timings:", json.dumps(timings))
    return 0 if not check.failed else 1


if __name__ == "__main__":
    sys.exit(main())
