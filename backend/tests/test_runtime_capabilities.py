from app.services import runtime_capabilities


def test_encoder_build_without_runtime_device_falls_back_to_cpu(monkeypatch):
    runtime_capabilities.reset_runtime_capabilities_cache()
    monkeypatch.setattr(runtime_capabilities, "_cuda_device_count", lambda: 0)
    monkeypatch.setattr(runtime_capabilities, "_ffmpeg_has_nvenc_encoder", lambda: True)
    monkeypatch.setattr(runtime_capabilities, "_probe_nvenc_runtime", lambda: False)

    capabilities = runtime_capabilities.get_runtime_capabilities()

    assert capabilities.ffmpeg_has_nvenc_encoder is True
    assert capabilities.nvenc_runtime_usable is False
    assert capabilities.label == "CPU"
    assert capabilities.gpu_compatible is False
    runtime_capabilities.reset_runtime_capabilities_cache()


def test_usable_cuda_and_nvenc_report_gpu(monkeypatch):
    runtime_capabilities.reset_runtime_capabilities_cache()
    monkeypatch.setattr(runtime_capabilities, "_cuda_device_count", lambda: 1)
    monkeypatch.setattr(runtime_capabilities, "_ffmpeg_has_nvenc_encoder", lambda: True)
    monkeypatch.setattr(runtime_capabilities, "_probe_nvenc_runtime", lambda: True)

    capabilities = runtime_capabilities.get_runtime_capabilities()

    assert capabilities.transcription_device == "cuda"
    assert capabilities.render_device == "gpu"
    assert capabilities.as_dict()["label"] == "GPU"
    runtime_capabilities.reset_runtime_capabilities_cache()
