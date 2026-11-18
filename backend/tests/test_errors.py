import subprocess

from app.core.errors import ErrorCode, PipelineError, classify_exception, describe_failure, sanitize_detail


def test_sanitize_removes_paths_and_secrets():
    raw = "ffmpeg failed reading /app/storage/uploads/abc.mp4 with token=supersecret and C:\\Users\\me\\x\\y.mp4"
    cleaned = sanitize_detail(raw)
    assert "/app/storage" not in cleaned and "supersecret" not in cleaned and "Users" not in cleaned
    assert "<path>/abc.mp4" in cleaned
    assert "token=[redacted]" in cleaned


def test_sanitize_truncates_from_the_end():
    assert len(sanitize_detail("x " * 1000, limit=50)) == 50


def test_classify_known_exceptions():
    assert classify_exception(PipelineError(ErrorCode.AUDIO_MISSING)) == ErrorCode.AUDIO_MISSING
    assert classify_exception(FileNotFoundError("gone")) == ErrorCode.SOURCE_MISSING
    assert classify_exception(subprocess.TimeoutExpired("ffprobe", 5)) == ErrorCode.SOURCE_PROBE_TIMEOUT
    assert classify_exception(RuntimeError("Transkripsi gagal: boom")) == ErrorCode.TRANSCRIPTION_FAILED
    assert classify_exception(RuntimeError("something else")) == ErrorCode.UNKNOWN


def test_describe_failure_returns_user_message_with_sanitized_detail():
    code, message = describe_failure(FileNotFoundError("/app/storage/uploads/a.mp4"))
    assert code == ErrorCode.SOURCE_MISSING
    assert message.startswith("File sumber tidak ditemukan")
    assert "/app/storage" not in message


def test_pipeline_error_message_includes_sanitized_detail():
    error = PipelineError(ErrorCode.EXPORT_FAILED, "stderr at /app/storage/temp/x.partial.mp4")
    assert str(error).startswith("Render klip gagal")
    assert error.detail == "stderr at <path>/x.partial.mp4"
