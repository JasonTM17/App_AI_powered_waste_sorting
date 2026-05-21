from pathlib import Path

import cv2
import numpy as np
import pytest

from app.core.events import Detection
from app.core.inference import InferenceEngine

MODEL = Path("models/best.pt")
FIXTURE = Path("tests/fixtures/sample_trash.jpg")


@pytest.mark.skipif(not MODEL.exists(), reason="best.pt missing")
def test_engine_loads_class_names():
    eng = InferenceEngine(MODEL, device="cpu")
    assert isinstance(eng.class_names, dict)
    assert len(eng.class_names) > 0


@pytest.mark.skipif(not (MODEL.exists() and FIXTURE.exists()), reason="missing assets")
def test_engine_predict_returns_detections():
    eng = InferenceEngine(MODEL, device="cpu", conf=0.05)
    img = cv2.imread(str(FIXTURE))
    out = eng.predict(img)
    assert isinstance(out, list)
    for d in out:
        assert isinstance(d, Detection)
        assert 0.0 <= d.conf <= 1.0


@pytest.mark.skipif(not MODEL.exists(), reason="best.pt missing")
def test_engine_predict_blank_frame():
    eng = InferenceEngine(MODEL, device="cpu")
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    out = eng.predict(blank)
    assert isinstance(out, list)
