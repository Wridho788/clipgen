"""
Centralized configuration. All paths/settings live here so nothing
is hardcoded across the codebase.
"""
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # --- Release ---
    app_version: str = "1.0.0"

    # --- Storage paths ---
    base_dir: Path = Path(__file__).resolve().parent.parent  # backend/
    storage_dir: Path = base_dir / "storage"
    upload_dir: Path = storage_dir / "uploads"
    clips_dir: Path = storage_dir / "clips"
    temp_dir: Path = storage_dir / "temp"
    log_dir: Path = base_dir / "logs"

    # --- Database ---
    database_url: str = f"sqlite:///{base_dir / 'storage' / 'app.db'}"

    # --- Whisper ---
    whisper_model_size: str = "tiny"  # tiny/base/small/medium — trade-off speed vs accuracy
    # `auto` resolves to CUDA only when the running container can actually use
    # it; the UI reports the resolved device instead of asking users to guess.
    whisper_device: Literal["auto", "cpu", "cuda"] = "auto"
    # Beam 5 is accurate but disproportionately slow for long-form CPU jobs.
    # Three beams retain useful transcript context while making throughput more
    # practical for the short-form selection workflow.
    whisper_beam_size: int = Field(default=3, ge=1, le=5)
    whisper_vad_filter: bool = True
    # Zero lets CTranslate2 select the CPU count exposed to the container.
    whisper_cpu_threads: int = Field(default=0, ge=0, le=64)
    # Conservative initial CPU estimate. The live RTF projection replaces it
    # once a job has processed enough audio.
    cpu_transcription_rtf: float = Field(default=1.75, ge=0.1, le=10.0)
    gpu_transcription_rtf: float = Field(default=0.35, ge=0.05, le=5.0)

    # --- Highlight detection thresholds ---
    highlight_window_seconds: float = 5.0
    # Short-form moments are scored dynamically; this is only a lower bound,
    # not a forced 15-second output length.
    highlight_min_clip_seconds: float = 10.0
    highlight_max_clip_seconds: float = 60.0
    # Zero means "auto" and is resolved from source duration at runtime.
    highlight_top_n: int = Field(default=0, ge=0, le=12)
    automatic_youtube_intro_skip_seconds: float = 60.0
    automatic_youtube_min_segment_gap_seconds: float = 15.0
    automatic_youtube_intro_analysis_seconds: float = 90.0
    automatic_youtube_intro_max_skip_seconds: float = 90.0

    # --- Ollama (metadata generation) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    ollama_timeout_seconds: int = 30
    ollama_num_predict: int = 220
    metadata_default_language: Literal["id", "en"] = "id"

    # --- YouTube download ---
    youtube_download_timeout_seconds: int = 900
    # Parallel fragment streams. Higher values can improve throughput but may be
    # throttled by YouTube, so keep the default deliberately conservative.
    youtube_download_concurrent_fragments: int = Field(default=4, ge=1, le=16)
    # 0 preserves yt-dlp's best-available-quality behavior.
    youtube_download_max_height: int = Field(default=720, ge=0, le=4320)
    # Optional Netscape-format cookies exported from a browser on the same
    # network.  Never put cookie contents in source control or job requests.
    youtube_cookies_path: Path | None = None
    youtube_user_agent: str | None = None

    # --- Rendering ---
    # Always automatic. Capability detection chooses an actually usable device
    # and exposes a label to the user.
    render_acceleration: Literal["auto"] = "auto"
    # Burn a consistent creator mark into every exported clip.  This is a
    # render default, not a player-only overlay, so downloaded files retain it.
    watermark_enabled: bool = True
    watermark_text: str = "@RidhoWahyu"
    watermark_opacity: float = Field(default=0.78, ge=0.1, le=1.0)
    watermark_position: Literal["bottom_right", "bottom_left", "top_right", "top_left"] = "bottom_right"

    # --- Upload limits ---
    max_upload_size_mb: int = 2048  # 2GB, wajar untuk video panjang personal use

    # --- Operations ---
    log_level: str = "INFO"
    log_json: bool = False
    log_rotation: str = "50 MB"
    log_retention_days: int = 7
    temp_cleanup_enabled: bool = True
    temp_cleanup_interval_hours: int = 6
    temp_file_retention_hours: int = 24
    upload_retention_days: int = 0  # 0 keeps source assets for retry/editing.
    clip_retention_days: int = 0  # 0 keeps exported clips until the user deletes them.
    requeue_pending_jobs_on_startup: bool = True
    # Interrupted work is deliberately left failed for an explicit user retry.
    # An automatic retry can otherwise monopolize the single local worker after a
    # restart and starve newly submitted jobs.
    transcription_timeout_min_seconds: int = 900
    # Long CPU transcriptions can legitimately exceed the conservative ETA.
    # Keep an explicit hard stop, but give a long source enough room to finish.
    transcription_timeout_multiplier: float = 4.0
    transcription_timeout_max_seconds: int = 14_400
    # A reporting cadence, not a failure threshold. Long FFmpeg/Ollama calls
    # may legitimately report every 30–60 seconds on slower devices.
    job_heartbeat_interval_seconds: int = 30

    # --- Local multi-user access (off by default to preserve personal setup) ---
    auth_enabled: bool = False
    auth_token_ttl_hours: int = 168
    auth_secret_key: str = "change-this-before-enabling-auth"


settings = Settings()

# Pastikan direktori storage selalu ada saat app start
for d in [settings.upload_dir, settings.clips_dir, settings.temp_dir, settings.log_dir]:
    d.mkdir(parents=True, exist_ok=True)
