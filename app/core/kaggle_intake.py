"""Safe-intake metadata for Kaggle Vietnam waste datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

KAGGLE_MINI_TRASH_VIETNAM_SOURCE = "kaggle_mini_trash_vietnam"
KAGGLE_GARBAGE_DETECTION_VN_SOURCE = "kaggle_garbage_detection_vn"
KAGGLE_VN_TRASH_CLASSIFICATION_SOURCE = "kaggle_vn_trash_classification"
KAGGLE_DOMESTIC_SOLID_WASTE_SOURCE = "kaggle_vietnam_domestic_solid_waste"
KAGGLE_GARBAGE_CLASSIFICATION_V2_SOURCE = "kaggle_garbage_classification_v2"
KAGGLE_AUTO_BBOX_CLASSIFICATION_SOURCE = "kaggle_auto_bbox_classification"

KAGGLE_TRAIN_SUPPORT_SOURCES = {
    KAGGLE_AUTO_BBOX_CLASSIFICATION_SOURCE,
    KAGGLE_MINI_TRASH_VIETNAM_SOURCE,
    KAGGLE_GARBAGE_DETECTION_VN_SOURCE,
    KAGGLE_GARBAGE_CLASSIFICATION_V2_SOURCE,
    KAGGLE_VN_TRASH_CLASSIFICATION_SOURCE,
    KAGGLE_DOMESTIC_SOLID_WASTE_SOURCE,
}


@dataclass(frozen=True)
class KaggleDatasetSpec:
    ref: str
    source_name: str
    expected_kind: str
    default_import: bool = False


KAGGLE_DATASETS = {
    "hoaalan/mini-trash-dataset-in-vietnam": KaggleDatasetSpec(
        ref="hoaalan/mini-trash-dataset-in-vietnam",
        source_name=KAGGLE_MINI_TRASH_VIETNAM_SOURCE,
        expected_kind="yolo_detection",
        default_import=True,
    ),
    "tiennnn123/garbage-detection-vn": KaggleDatasetSpec(
        ref="tiennnn123/garbage-detection-vn",
        source_name=KAGGLE_GARBAGE_DETECTION_VN_SOURCE,
        expected_kind="unknown_until_audit",
    ),
    "mrgetshjtdone/vn-trash-classification": KaggleDatasetSpec(
        ref="mrgetshjtdone/vn-trash-classification",
        source_name=KAGGLE_VN_TRASH_CLASSIFICATION_SOURCE,
        expected_kind="classification_or_unknown",
    ),
    "thanhngnguyn/vietnam-domestic-solid-waste": KaggleDatasetSpec(
        ref="thanhngnguyn/vietnam-domestic-solid-waste",
        source_name=KAGGLE_DOMESTIC_SOLID_WASTE_SOURCE,
        expected_kind="large_unknown_until_audit",
    ),
    "sumn2u/garbage-classification-v2": KaggleDatasetSpec(
        ref="sumn2u/garbage-classification-v2",
        source_name=KAGGLE_GARBAGE_CLASSIFICATION_V2_SOURCE,
        expected_kind="classification_or_unknown",
    ),
}


def source_for_kaggle_ref(ref: str) -> str:
    spec = KAGGLE_DATASETS.get(ref)
    if spec is not None:
        return spec.source_name
    slug = ref.strip().replace("/", "_").replace("-", "_").lower()
    return f"kaggle_{slug}" if slug else "kaggle_unknown"


def likely_dataset_kind(root: Path, *, image_count: int, label_count: int) -> str:
    if label_count > 0 and _has_images_dir(root):
        return "yolo_detection"
    if image_count > 0 and _has_class_directories(root):
        return "classification_only"
    if image_count > 0:
        return "image_pack_needs_review"
    return "unknown"


def _has_images_dir(root: Path) -> bool:
    return any(part.lower() == "images" for path in root.rglob("*") for part in path.parts)


def _has_class_directories(root: Path) -> bool:
    image_parent_names = {
        path.parent.name
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    }
    return len(image_parent_names - {"images", "train", "test", "valid", "val"}) >= 2


__all__ = [
    "KAGGLE_AUTO_BBOX_CLASSIFICATION_SOURCE",
    "KAGGLE_DATASETS",
    "KAGGLE_DOMESTIC_SOLID_WASTE_SOURCE",
    "KAGGLE_GARBAGE_CLASSIFICATION_V2_SOURCE",
    "KAGGLE_GARBAGE_DETECTION_VN_SOURCE",
    "KAGGLE_MINI_TRASH_VIETNAM_SOURCE",
    "KAGGLE_TRAIN_SUPPORT_SOURCES",
    "KAGGLE_VN_TRASH_CLASSIFICATION_SOURCE",
    "KaggleDatasetSpec",
    "likely_dataset_kind",
    "source_for_kaggle_ref",
]
