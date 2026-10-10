"""
Manual test script untuk verify setiap pipeline stage berjalan.
Jalankan: python test_pipeline.py <path_ke_video_test>

Siapkan video test ~30-60 detik dengan audio jelas (podcast/vlog).
"""
import sys
import time
from pathlib import Path

from app.core.pipeline import (
    audio_extract,
    transcribe,
    clip_cut,
    smart_crop,
    metadata_gen,
)
from app.config import settings


def test_pipeline(video_path: Path):
    if not video_path.exists():
        print(f"❌ File tidak ditemukan: {video_path}")
        return False

    print(f"🎥 Testing pipeline dengan: {video_path.name}\n")
    t_start = time.time()

    # Stage 1
    print("[1/7] Extract audio...")
    t0 = time.time()
    audio_path = audio_extract.extract_audio(video_path, settings.temp_dir)
    print(f"✅ Audio: {audio_path.name} ({time.time()-t0:.1f}s)\n")

    # Stage 2
    print("[2/7] Transcribe (Whisper)...")
    t0 = time.time()
    segments = transcribe.transcribe(audio_path)
    print(f"✅ {len(segments)} segments ({time.time()-t0:.1f}s)")
    for seg in segments[:3]:
        print(f"   {seg.start:.1f}-{seg.end:.1f}s: {seg.text[:60]}")
    print()

    if not segments:
        print("⚠️  Tidak ada speech terdeteksi. Cek audio source.")
        return False

    # Stage 3-6: use the first configured clip window.
    clip_start = 0.0
    clip_end = min(segments[-1].end, settings.highlight_max_clip_seconds)
    clip_id = "test-clip-001"

    print("[4/7] Cut clip...")
    t0 = time.time()
    raw_clip = clip_cut.cut_clip(video_path, clip_start, clip_end, settings.clips_dir, clip_id)
    print(f"✅ {raw_clip.name} ({time.time()-t0:.1f}s)\n")

    print("[5/7] Smart crop (OpenCV face detection + center fallback)...")
    t0 = time.time()
    cropped = smart_crop.smart_crop(raw_clip, settings.clips_dir, clip_id)
    print(f"✅ {cropped.name} ({time.time()-t0:.1f}s)\n")

    print("[6/6] Generate metadata (Ollama)...")
    t0 = time.time()
    clip_text = " ".join(s.text for s in segments if s.start >= clip_start and s.end <= clip_end)
    metadata = metadata_gen.generate_metadata(clip_text)
    print(f"✅ Metadata ({time.time()-t0:.1f}s)")
    print(f"   Title: {metadata['title']}")
    print(f"   Caption: {metadata['caption'][:80]}")
    print(f"   Hashtags: {metadata['hashtags']}\n")

    total_time = time.time() - t_start
    print(f"✅ SEMUA STAGE BERHASIL. Total waktu: {total_time:.1f}s")
    print(f"📹 Output final: {cropped}")
    print(f"   Preview: ffplay '{cropped}'")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_pipeline.py <path_ke_video.mp4>")
        sys.exit(1)

    video = Path(sys.argv[1])
    success = test_pipeline(video)
    sys.exit(0 if success else 1)
