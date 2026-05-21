import json
from pathlib import Path

import cv2
import numpy as np

from app.ui.pages.capture import export_yolo_dataset


def _make_frame(qdir: Path, uid: str, boxes):
    qdir.mkdir(parents=True, exist_ok=True)
    img = np.full((480, 640, 3), 200, dtype=np.uint8)
    cv2.imwrite(str(qdir / f"{uid}.jpg"), img)
    meta = {"ts": "2026-05-21T10:00:00", "boxes": boxes}
    (qdir / f"{uid}.json").write_text(json.dumps(meta), encoding="utf-8")


def test_export_writes_data_yaml_and_labels(tmp_path):
    qdir = tmp_path / "queue"
    out = tmp_path / "out"
    _make_frame(qdir, "abc", [
        {"cls_id": 0, "cls_name": "paper", "conf": 0.5, "xyxy": [100, 100, 200, 200]},
    ])
    _make_frame(qdir, "def", [
        {"cls_id": 1, "cls_name": "plastic", "conf": 0.4, "xyxy": [10, 10, 50, 50]},
    ])
    n = export_yolo_dataset(qdir, out)
    assert n == 2
    assert (out / "data.yaml").exists()
    yaml = (out / "data.yaml").read_text(encoding="utf-8")
    assert "paper" in yaml and "plastic" in yaml
    assert (out / "images" / "abc.jpg").exists()
    label_text = (out / "labels" / "abc.txt").read_text(encoding="utf-8")
    parts = label_text.strip().split()
    assert parts[0] == "0"
    cx, cy, w, h = (float(x) for x in parts[1:])
    assert abs(cx - 0.234375) < 0.01
    assert 0 <= cx <= 1


def test_export_handles_empty_queue(tmp_path):
    n = export_yolo_dataset(tmp_path / "missing", tmp_path / "out2")
    assert n == 0
    assert (tmp_path / "out2" / "data.yaml").exists()
