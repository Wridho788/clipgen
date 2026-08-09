"""
Integration test untuk API endpoints (butuh backend running di localhost:8000).
Jalankan: python test_api.py <path_ke_video.mp4>
"""
import sys
import time
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000"


def upload_video(video_path: Path) -> str:
    print(f"[TEST] POST /api/videos/upload ({video_path.name})")
    with open(video_path, "rb") as f:
        r = requests.post(f"{BASE_URL}/api/videos/upload", files={"file": f})
    r.raise_for_status()
    job_id = r.json()["job_id"]
    print(f"✅ job_id={job_id}\n")
    return job_id


def poll_until_done(job_id: str, timeout=3600, interval=5) -> dict:
    print(f"[TEST] Polling GET /api/jobs/{job_id} setiap {interval}s...")
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{BASE_URL}/api/jobs/{job_id}")
        r.raise_for_status()
        job = r.json()
        print(f"   status={job['status']}, progress={job['progress']}%")

        if job["status"] in ("done", "failed", "cancelled"):
            return job
        time.sleep(interval)

    raise TimeoutError(f"Job {job_id} tidak selesai dalam {timeout}s")


def get_clips(job_id: str) -> list:
    print(f"\n[TEST] GET /api/clips/job/{job_id}")
    r = requests.get(f"{BASE_URL}/api/clips/job/{job_id}")
    r.raise_for_status()
    clips = r.json()
    print(f"✅ {len(clips)} clips ditemukan")
    for c in clips:
        print(f"   {c['id']}: {c.get('title')} [{c['status']}]")
    return clips


def download_clip(clip_id: str, output_dir: Path = Path(".")):
    print(f"\n[TEST] GET /api/clips/{clip_id}/file")
    r = requests.get(f"{BASE_URL}/api/clips/{clip_id}/file", stream=True)
    r.raise_for_status()

    out = output_dir / f"downloaded_{clip_id}.mp4"
    with open(out, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"✅ {out.name} ({size_mb:.1f}MB)")


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_api.py <path_ke_video.mp4>")
        sys.exit(1)

    video_path = Path(sys.argv[1])
    if not video_path.exists():
        print(f"❌ File tidak ditemukan: {video_path}")
        sys.exit(1)

    # Sanity check: backend hidup?
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        r.raise_for_status()
        print(f"✅ Backend healthy: {r.json()}\n")
    except Exception as e:
        print(f"❌ Backend tidak bisa diakses di {BASE_URL}: {e}")
        print("   Pastikan `docker-compose up -d` sudah jalan.")
        sys.exit(1)

    job_id = upload_video(video_path)
    job = poll_until_done(job_id)

    if job["status"] != "done":
        print(f"\n❌ Job berakhir dengan status: {job['status']}")
        print(f"   Error: {job.get('error_message')}")
        sys.exit(1)

    clips = get_clips(job_id)
    if not clips:
        print("\n⚠️  Job selesai tapi 0 clips dihasilkan (highlight detection kosong).")
        sys.exit(1)

    ready_clips = [c for c in clips if c["status"] == "ready"]
    if ready_clips:
        download_clip(ready_clips[0]["id"])

    print(f"\n✅ END-TO-END TEST PASSED ({len(ready_clips)}/{len(clips)} clips ready)")


if __name__ == "__main__":
    main()
