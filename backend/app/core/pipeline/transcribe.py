"""Whisper transcription with progress reporting and a killable timeout boundary."""
from __future__ import annotations

from dataclasses import dataclass, field
from multiprocessing import get_context
from pathlib import Path
from queue import Empty
from time import monotonic
import traceback
from typing import Callable

from loguru import logger

from app.config import settings
from app.services.runtime_capabilities import get_runtime_capabilities


@dataclass
class Word:
    """A word-level timestamp used for karaoke captions when available."""

    start: float
    end: float
    text: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)


class TranscriptionTimeoutError(RuntimeError):
    """Raised after terminating a Whisper child that exceeded its job timeout."""


ProgressCallback = Callable[[float | None], None]


def _transcribe_worker(
    audio_path: str,
    model_size: str,
    device: str,
    cpu_threads: int,
    include_word_timestamps: bool,
    message_queue,
    report_every_seconds: float,
) -> None:
    """Run CTranslate2 outside the API process and stream compact progress events."""
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(
            model_size,
            device=device,
            compute_type="int8" if device == "cpu" else "float16",
            cpu_threads=cpu_threads,
        )
        segments_iter, info = model.transcribe(
            audio_path,
            beam_size=settings.whisper_beam_size,
            vad_filter=settings.whisper_vad_filter,
            word_timestamps=include_word_timestamps,
        )
        segments: list[dict[str, float | str]] = []
        last_reported_end = 0.0

        for segment in segments_iter:
            start = float(segment.start)
            end = float(segment.end)
            words = [
                {
                    "start": float(word.start if word.start is not None else start),
                    "end": float(word.end if word.end is not None else end),
                    "text": str(word.word).strip(),
                }
                for word in (segment.words or [])
                if str(word.word).strip()
            ]
            segments.append({"start": start, "end": end, "text": segment.text.strip(), "words": words})
            if end - last_reported_end >= report_every_seconds:
                message_queue.put(("progress", end))
                last_reported_end = end

        if segments and float(segments[-1]["end"]) > last_reported_end:
            message_queue.put(("progress", float(segments[-1]["end"])))
        message_queue.put(
            (
                "result",
                {
                    "segments": segments,
                    "language": str(info.language),
                    "language_probability": float(info.language_probability),
                },
            )
        )
    except BaseException:
        message_queue.put(("error", traceback.format_exc(limit=12)))


def transcribe(
    audio_path: Path,
    *,
    on_progress: ProgressCallback | None = None,
    timeout_seconds: int | None = None,
    heartbeat_interval_seconds: int | None = None,
    include_word_timestamps: bool = False,
) -> list[Segment]:
    """Return timestamped segments while keeping the worker cancellable.

    Faster-Whisper spends most of the stage inside native CPU code. It therefore
    runs in a dedicated process: a normal thread or ``asyncio`` timeout cannot
    stop that work. The parent terminates the child on timeout or when the
    progress callback raises (for example after the user cancels the job).
    """
    timeout = int(timeout_seconds or settings.transcription_timeout_max_seconds)
    heartbeat_interval = max(1, int(heartbeat_interval_seconds or settings.job_heartbeat_interval_seconds))
    requested_device = settings.whisper_device
    capabilities = get_runtime_capabilities()
    if requested_device == "cuda" and capabilities.cuda_device_count <= 0:
        logger.warning("CUDA transcription requested but unavailable; using CPU")
    device = (
        "cuda"
        if requested_device != "cpu" and capabilities.cuda_device_count > 0
        else "cpu"
    )
    context = get_context("spawn")
    messages = context.Queue()
    process = context.Process(
        target=_transcribe_worker,
        args=(
            str(audio_path),
            settings.whisper_model_size,
            device,
            settings.whisper_cpu_threads,
            include_word_timestamps,
            messages,
            10.0,
        ),
        name=f"clipgen-whisper-{audio_path.stem[:8]}",
    )

    logger.info(
        f"Transcribing in isolated worker: {audio_path.name} "
        f"(device={device}, words={include_word_timestamps}, timeout={timeout}s)"
    )
    process.start()
    deadline = monotonic() + timeout
    last_heartbeat = monotonic()

    try:
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TranscriptionTimeoutError(
                    f"Transkripsi melewati batas waktu {timeout // 60} menit dan dihentikan."
                )

            now = monotonic()
            if on_progress is not None and now - last_heartbeat >= heartbeat_interval:
                on_progress(None)
                last_heartbeat = now

            try:
                event, payload = messages.get(timeout=min(1.0, remaining))
            except Empty:
                if not process.is_alive():
                    try:
                        event, payload = messages.get_nowait()
                    except Empty as error:
                        raise RuntimeError(
                            f"Worker transkripsi berhenti tanpa hasil (exit code {process.exitcode})."
                        ) from error
                else:
                    continue

            if event == "progress":
                if on_progress is not None:
                    on_progress(float(payload))
                last_heartbeat = monotonic()
                continue
            if event == "error":
                raise RuntimeError(f"Transkripsi gagal: {payload[-800:]}")
            if event == "result":
                raw_segments = payload["segments"]
                segments = [
                    Segment(
                        start=float(item["start"]),
                        end=float(item["end"]),
                        text=str(item["text"]),
                        words=[
                            Word(
                                start=float(word["start"]),
                                end=float(word["end"]),
                                text=str(word["text"]),
                            )
                            for word in item.get("words", [])
                            if isinstance(word, dict)
                        ],
                    )
                    for item in raw_segments
                ]
                logger.info(
                    f"Transcription done: {len(segments)} segments, "
                    f"detected language={payload['language']} (p={payload['language_probability']:.2f})"
                )
                return segments
            raise RuntimeError(f"Worker transkripsi mengirim event tidak dikenal: {event}")
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=2)
        messages.close()
        messages.join_thread()
