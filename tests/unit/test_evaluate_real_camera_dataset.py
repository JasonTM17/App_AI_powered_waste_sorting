from __future__ import annotations

import json

import cv2
import numpy as np

from scripts.evaluate_real_camera_dataset import blur_bucket, collect_samples, summarize_samples


def test_collect_samples_keeps_reviewed_blurry_camera_truth(tmp_path):
    image = np.full((80, 120, 3), 180, dtype=np.uint8)
    image_path = tmp_path / "camera-spoon.jpg"
    cv2.imwrite(str(image_path), image)
    image_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_camera_capture",
                "reviewed": True,
                "bbox_reviewed": True,
                "training_excluded": False,
                "boxes": [{"cls_id": 13, "cls_name": "Iron utensils", "xyxy": [5, 5, 110, 70]}],
            }
        ),
        encoding="utf-8",
    )

    samples, skipped = collect_samples(tmp_path)

    assert skipped == {}
    assert len(samples) == 1
    assert samples[0]["boxes"][0]["class_name"] == "Iron utensils"
    assert blur_bucket(samples[0]["blur_score"]) == "blurry_real_camera"


def test_collect_samples_rejects_unreviewed_and_augmented_sources(tmp_path):
    image = np.full((32, 32, 3), 128, dtype=np.uint8)
    for name, source, reviewed in (
        ("unreviewed", "manual_camera_capture", False),
        ("augmented", "camera_blur_augmented", True),
    ):
        path = tmp_path / f"{name}.jpg"
        cv2.imwrite(str(path), image)
        path.with_suffix(".json").write_text(
            json.dumps(
                {
                    "source": source,
                    "reviewed": reviewed,
                    "bbox_reviewed": reviewed,
                    "boxes": [{"cls_id": 42, "cls_name": "Pen", "xyxy": [1, 1, 30, 30]}],
                }
            ),
            encoding="utf-8",
        )

    samples, skipped = collect_samples(tmp_path)

    assert samples == []
    assert skipped["not_reviewed"] == 1


def test_summary_reports_camera_domain_gaps():
    summary = summarize_samples(
        [
            {
                "boxes": [{"class_name": "Pen"}, {"class_name": "Iron utensils"}],
                "blur_score": 50.0,
                "split": "train",
            }
        ]
    )

    assert summary["represented_classes"] == 2
    assert summary["blur_buckets"] == {"blurry_real_camera": 1}
    assert "Plastic bottle" in summary["missing_classes"]
