import json

import pytest
from PIL import Image

from app.core.licensed_source_ingestion import (
    source_manifest_issues,
    validate_manual_url_source,
)
from app.core.source_quality_report import build_source_quality_report


def _write_item(queue, name: str, color=(80, 80, 80), **meta_extra):
    image_path = queue / f"{name}.jpg"
    Image.new("RGB", (64, 48), color).save(image_path)
    meta = {
        "source": "manual_web_import",
        "reviewed": True,
        "source_url": "https://example.test/image.jpg",
        "source_page_url": "https://example.test/page",
        "source_license": "CC-BY-4.0",
        "source_author": "Example Author",
        "source_type": "wikimedia",
        "canonical_class": "Pen",
        "boxes": [{"cls_id": 42, "cls_name": "Pen", "conf": 1.0, "xyxy": [4, 4, 60, 44]}],
    }
    meta.update(meta_extra)
    image_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    return image_path


def test_validate_manual_url_source_requires_license_manifest_fields():
    with pytest.raises(ValueError) as err:
        validate_manual_url_source(
            class_name="Pen",
            source_url="https://example.test/pen.jpg",
            source_page_url="",
            source_license="CC-BY",
            source_author="",
            source_type="wikimedia",
            generated=False,
        )

    assert "source_page_url" in str(err.value)
    assert "source_author" in str(err.value)


def test_validate_manual_url_source_marks_generated_train_only():
    meta = validate_manual_url_source(
        class_name="but bi",
        source_url="https://example.test/pen.jpg",
        source_page_url="https://example.test/page",
        source_license="generated-training-only",
        source_author="local-generator",
        source_type="generated",
        generated=True,
    )

    assert meta["canonical_class"] == "Pen"
    assert meta["generated"] is True
    assert meta["recognition_enabled"] is False
    assert meta["split"] == "train"
    assert meta["split_lock"] is True


def test_source_quality_report_flags_blur_duplicates_and_missing_manifest(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    first = _write_item(queue, "first")
    duplicate = queue / "duplicate.jpg"
    duplicate.write_bytes(first.read_bytes())
    duplicate.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_web_import",
                "reviewed": True,
                "boxes": [{"cls_id": 42, "cls_name": "Pen", "conf": 1.0, "xyxy": [4, 4, 60, 44]}],
            }
        ),
        encoding="utf-8",
    )

    report = build_source_quality_report(queue)

    assert report["duplicate_images"] == 1
    assert report["blurry_images"] >= 1
    assert report["invalid_source_images"] == 1
    pen = next(row for row in report["classes"] if row["class_name"] == "Pen")
    assert pen["priority"] == "P0"
    assert pen["source_issue_count"] > 0


def test_source_manifest_issues_require_augmented_parent_and_profile():
    issues = source_manifest_issues(
        {
            "source": "camera_blur_augmented",
            "source_type": "camera_blur_augmented",
            "camera_blur_augmented": True,
            "canonical_class": "Pen",
            "split": "valid",
            "recognition_enabled": True,
        }
    )

    assert "missing_augmentation_parent" in issues
    assert "missing_augmentation_profile" in issues
    assert "augmented_not_train_split" in issues
    assert "augmented_reference_enabled" in issues
