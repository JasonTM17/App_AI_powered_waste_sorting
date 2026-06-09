from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.image_embedding import LegacyImageEmbedder
from app.core.kaggle_real_image_pipeline import (
    GARBAGE_CLASSIFICATION_V2_REF,
    iter_classification_rows,
    write_manifest,
)
from app.core.three_bin_classifier import ThreeBinClassifier
from scripts.export_kaggle_three_bin_classifier_dataset import _manifest_rows


def test_phase21_garbage_classification_v2_maps_folder_labels_to_three_bins(tmp_path: Path):
    root = tmp_path / "garbage-v2"
    _write_image(root / "garbage-dataset" / "train" / "battery" / "battery.jpg")
    _write_image(root / "garbage-dataset" / "valid" / "biological" / "organic.jpg")
    _write_image(root / "garbage-dataset" / "test" / "white-glass" / "glass.jpg")

    rows = list(iter_classification_rows(root, GARBAGE_CLASSIFICATION_V2_REF))

    by_class = {row.source_class: row for row in rows}
    assert by_class["battery"].canonical_class == "Battery"
    assert by_class["battery"].bin_code == "R"
    assert by_class["biological"].canonical_class == "Organic"
    assert by_class["biological"].bin_code == "O"
    assert by_class["white-glass"].canonical_class == "Glass bottle"
    assert by_class["white-glass"].bin_code == "I"
    assert by_class["white-glass"].classifier_split == "test"


def test_phase21_classifier_export_keeps_classification_images_as_missing_bbox(tmp_path: Path):
    root = tmp_path / "garbage-v2"
    _write_image(root / "garbage-dataset" / "train" / "trash" / "trash.jpg")
    rows = list(iter_classification_rows(root, GARBAGE_CLASSIFICATION_V2_REF))
    manifest = tmp_path / "classification.jsonl"
    summary = tmp_path / "summary.json"
    write_manifest(rows, manifest, summary)

    exported = _manifest_rows(manifest, max_per_bin=0, max_per_class=0)

    assert len(exported) == 1
    assert exported[0]["bin_code"] == "R"
    assert exported[0]["canonical_class"] == "Unknown plastic"
    assert exported[0]["bbox_status"] == "missing"
    assert exported[0]["input_type"] == "classification_image"


def test_three_bin_centroid_classifier_passes_confidence_and_margin(tmp_path: Path):
    red = np.full((32, 32, 3), (230, 20, 20), dtype=np.uint8)
    green = np.full((32, 32, 3), (20, 230, 20), dtype=np.uint8)
    blue = np.full((32, 32, 3), (20, 20, 230), dtype=np.uint8)
    embedder = LegacyImageEmbedder()
    artifact = {
        "backend": "legacy_centroid",
        "centroids": {
            "O": embedder.embed(red).tolist(),
            "R": embedder.embed(green).tolist(),
            "I": embedder.embed(blue).tolist(),
        },
    }
    artifact_path = tmp_path / "three-bin.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    classifier = ThreeBinClassifier(
        artifact_path,
        enabled=True,
        min_confidence=0.4,
        min_margin=0.05,
        min_crop_area_ratio=0.0,
    )

    pred = classifier.classify_rgb(red)

    assert pred is not None
    assert pred.command == "O"
    assert pred.cls_name == "Kaggle 3-bin O"
    assert pred.passed is True


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 32), (190, 190, 190)).save(path)
