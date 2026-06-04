import json

import numpy as np

from app.core.dataset_catalog import DatasetCatalog
from app.core.dataset_trust import DatasetTrustState, classify_dataset_item, is_trainable_meta
from app.core.events import Detection
from app.core.hard_negative_dataset import capture_hard_negative_frame
from scripts.export_safety_eval_pack import export_safety_eval_pack
from scripts.run_safety_eval import _evaluate_expected_outcome


def test_capture_hard_negative_is_evaluation_only_and_cataloged(tmp_path):
    queue = tmp_path / "queue"
    catalog_path = tmp_path / "dataset.db"
    frame = np.full((40, 60, 3), 120, dtype=np.uint8)

    image_path = capture_hard_negative_frame(
        frame,
        queue,
        "hand_only",
        catalog_path=catalog_path,
        extra_meta={"detection_context": [{"cls_name": "Aluminum can", "conf": 0.58}]},
    )

    meta = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
    decision = classify_dataset_item(meta)
    assert meta["source"] == "hard_negative"
    assert meta["hard_negative_reason"] == "hand_only"
    assert meta["expected_outcome"] == "no_dispatch"
    assert meta["training_excluded"] is True
    assert meta["evaluation_enabled"] is True
    assert meta["boxes"] == []
    assert is_trainable_meta(meta) is False
    assert decision.state is DatasetTrustState.HARD_NEGATIVE

    catalog = DatasetCatalog(catalog_path)
    try:
        row = catalog.get_item(image_path.stem)
        assert row is not None
        assert row["source"] == "hard_negative"
        assert catalog.list_boxes(image_path.stem) == []
    finally:
        catalog.close()


def test_safety_eval_export_uses_only_hard_negatives_and_writes_no_labels(tmp_path):
    queue = tmp_path / "queue"
    capture_hard_negative_frame(np.zeros((20, 20, 3), dtype=np.uint8), queue, "cloth_non_waste")
    normal = queue / "normal.jpg"
    normal.write_bytes((queue / next(queue.glob("*.jpg")).name).read_bytes())
    normal.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_import",
                "boxes": [{"cls_id": 18, "cls_name": "Paper", "xyxy": [1, 1, 10, 10]}],
            }
        ),
        encoding="utf-8",
    )

    out = tmp_path / "safety"
    summary = export_safety_eval_pack(queue, out)

    assert summary["total"] == 1
    assert summary["by_reason"] == {"cloth_non_waste": 1}
    assert not (out / "labels").exists()
    rows = [
        json.loads(line)
        for line in (out / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[0]["expected_outcome"] == "no_dispatch"
    assert (out / rows[0]["image"]).exists()


def test_safety_eval_multi_object_accepts_same_class_pair():
    ok, detail = _evaluate_expected_outcome(
        "multi_object_warning",
        [
            Detection(42, "Pen", 0.9, (0, 0, 10, 10)),
            Detection(42, "Pen", 0.8, (20, 0, 30, 10)),
        ],
        None,
    )

    assert ok is True
    assert "detections=2" in detail
