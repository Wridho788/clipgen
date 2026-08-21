"""Runtime acceleration detection used by processing and UI status.

An FFmpeg binary can advertise NVENC even when no NVIDIA driver/device is
attached to Docker.  This module performs a small runtime probe once and keeps
the result cached, so the application can label work honestly and avoid a
failed encoder attempt for every clip.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import subprocess

from loguru import logger


@dataclass(frozen=True)
class RuntimeCapabilities:
    cuda_device_count: int
    ffmpeg_has_nvenc_encoder: bool
    nvenc_runtime_usable: bool

    @property
    def transcription_device(self) -> str:
        return "cuda" if self.cuda_device_count > 0 else "cpu"

    @property
    def render_device(self) -> str:
        return "gpu" if self.nvenc_runtime_usable else "cpu"

    @property
    def gpu_compatible(self) -> bool:
        return self.cuda_device_count > 0 or self.nvenc_runtime_usable

    @property
    def label(self) -> str:
        if self.transcription_device == "cuda" and self.render_device == "gpu":
            return "GPU"
        if self.transcription_device == "cuda":
            return "GPU transkripsi · CPU render"
        if self.render_device == "gpu":
            return "CPU transkripsi · GPU render"
        return "CPU"

    def as_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "default_mode": "auto",
            "label": self.label,
            "transcription_device": self.transcription_device,
            "render_device": self.render_device,
            "gpu_compatible": self.gpu_compatible,
        }


def _cuda_device_count() -> int:
    try:
        import ctranslate2

        return max(0, int(ctranslate2.get_cuda_device_count()))
    except Exception as error:  # Optional capability: never block CPU operation.
        logger.debug(f"CUDA capability unavailable: {error}")
        return 0


def _ffmpeg_has_nvenc_encoder() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        logger.debug(f"FFmpeg encoder list unavailable: {error}")
        return False
    return result.returncode == 0 and "h264_nvenc" in result.stdout


def _probe_nvenc_runtime() -> bool:
    """Encode one synthetic frame to distinguish build support from real GPU access."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=16x16:d=0.04",
                "-frames:v",
                "1",
                "-c:v",
                "h264_nvenc",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        logger.debug(f"NVENC runtime probe unavailable: {error}")
        return False
    if result.returncode != 0:
        logger.info("NVENC encoder is present in FFmpeg but unavailable at runtime; using CPU render")
    return result.returncode == 0


@lru_cache(maxsize=1)
def get_runtime_capabilities() -> RuntimeCapabilities:
    """Inspect the active process/container once; CPU is always a safe fallback."""
    has_nvenc_encoder = _ffmpeg_has_nvenc_encoder()
    return RuntimeCapabilities(
        cuda_device_count=_cuda_device_count(),
        ffmpeg_has_nvenc_encoder=has_nvenc_encoder,
        nvenc_runtime_usable=has_nvenc_encoder and _probe_nvenc_runtime(),
    )


def reset_runtime_capabilities_cache() -> None:
    """Test/support hook when a container is deliberately reconfigured."""
    get_runtime_capabilities.cache_clear()
