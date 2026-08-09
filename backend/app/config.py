"""
Centralized configuration. All paths/settings live here so nothing
is hardcoded across the codebase.
"""
from pathlib import Path
from typing import Literal

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
    whisper_device: str = "cpu"  # ganti ke "cuda" kalau ada GPU

    # --- Highlight detection thresholds ---
    highlight_window_seconds: float = 5.0
    highlight_min_clip_seconds: float = 15.0
    highlight_max_clip_seconds: float = 60.0
    highlight_top_n: int = 5
    automatic_youtube_intro_skip_seconds: float = 60.0
    automatic_youtube_min_segment_gap_seconds: float = 15.0

    # --- Ollama (metadata generation) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    ollama_timeout_seconds: int = 30
    ollama_num_predict: int = 220
    metadata_default_language: Literal["id", "en"] = "id"

    # --- YouTube download ---
    youtube_download_timeout_seconds: int = 900

    # --- Upload limits ---
    max_upload_size_mb: int = 2048  # 2GB, wajar untuk video panjang personal use

    # --- Operations ---
    log_level: str = "INFO"
    log_rotation: str = "50 MB"
    log_retention_days: int = 7
    temp_cleanup_enabled: bool = True
    temp_cleanup_interval_hours: int = 6
    temp_file_retention_hours: int = 24
    requeue_pending_jobs_on_startup: bool = True


settings = Settings()

# Pastikan direktori storage selalu ada saat app start
for d in [settings.upload_dir, settings.clips_dir, settings.temp_dir, settings.log_dir]:
    d.mkdir(parents=True, exist_ok=True)
