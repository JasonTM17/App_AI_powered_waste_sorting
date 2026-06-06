from app.core import inference


def test_resolve_inference_device_auto_prefers_cuda(monkeypatch):
    monkeypatch.setattr(inference, "_cuda_available", lambda: True)

    device, label = inference.resolve_inference_device("auto")

    assert device == "0"
    assert label == "cuda:0"


def test_resolve_inference_device_auto_falls_back_to_cpu(monkeypatch):
    monkeypatch.setattr(inference, "_cuda_available", lambda: False)

    device, label = inference.resolve_inference_device("auto")

    assert device == "cpu"
    assert label == "cpu"


def test_resolve_inference_device_cpu_stays_cpu(monkeypatch):
    monkeypatch.setattr(inference, "_cuda_available", lambda: True)

    device, label = inference.resolve_inference_device("cpu")

    assert device == "cpu"
    assert label == "cpu"
