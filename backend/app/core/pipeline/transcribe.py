"""
Stage 2: Transkripsi audio -> teks + timestamp per segmen.
Menggunakan faster-whisper (CTranslate2 backend) — lebih cepat &
lebih ringan CPU dibanding openai-whisper original untuk kebutuhan lokal.
"""
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from app.config import settings


@dataclass
class Segment:
    start: float
    end: float
    text: str


_model = None  # lazy-loaded singleton, model besar, jangan load berkali-kali


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info(f"Loading Whisper model: {settings.whisper_model_size}")
        _model = WhisperModel(
            settings.whisper_model_size,
            device=settings.whisper_device,
            compute_type="int8" if settings.whisper_device == "cpu" else "float16",
        )
    return _model


def transcribe(audio_path: Path) -> list[Segment]:
    """
    Return list segmen dengan timestamp. Model di-load sekali dan
    dipakai ulang lintas job (menghemat waktu load ~beberapa detik-menit
    tergantung ukuran model).
    """
    model = _get_model()
    logger.info(f"Transcribing: {audio_path.name}")

    segments_iter, info = model.transcribe(str(audio_path), beam_size=5)

    segments = [
        Segment(start=seg.start, end=seg.end, text=seg.text.strip())
        for seg in segments_iter
    ]

    logger.info(
        f"Transcription done: {len(segments)} segments, "
        f"detected language={info.language} (p={info.language_probability:.2f})"
    )
    return segments
