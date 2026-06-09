"""Phase 20 helpers for Kaggle real-image classification datasets."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.kaggle_intake import (
    KAGGLE_DOMESTIC_SOLID_WASTE_SOURCE,
    KAGGLE_GARBAGE_CLASSIFICATION_V2_SOURCE,
    KAGGLE_VN_TRASH_CLASSIFICATION_SOURCE,
)
from app.core.waste_categories import (
    WasteCategory,
    canonical_class_name,
    category_for_class,
)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

VN_TRASH_CLASSIFICATION_REF = "mrgetshjtdone/vn-trash-classification"
DOMESTIC_SOLID_WASTE_REF = "thanhngnguyn/vietnam-domestic-solid-waste"
GARBAGE_CLASSIFICATION_V2_REF = "sumn2u/garbage-classification-v2"

VN_TRASH_CLASS_MAP = {
    "Alu": "Aluminum can",
    "Carton": "Cardboard",
    "Foam_box": "Disposable tableware",
    "Milk_box": "Tetra pack",
    "Other": "Unknown plastic",
    "PET": "Plastic bottle",
    "Paper": "Paper",
    "Paper_cup": "Paper cups",
    "Plastic_cup": "Plastic cup",
}

DOMESTIC_SOLID_WASTE_CLASS_MAP = {
    "111_Paper_box": "Cardboard",
    "112_Paper_other": "Paper",
    "121_Plastic_box": "Combined plastic",
    "122_Plastic_cups": "Plastic cup",
    "131_Metal_package": "Tin",
    "132_Metal_other": "Scrap metal",
    "141_Glass_bottle": "Glass bottle",
    "143_Glass_other": "Glass bottle",
    "151_Fabric_leather": "Textile",
    "161_Wood_household": "Wood",
    "171_Rubber_toy": "Plastic toys",
    "172_Rubber_other": "Unknown plastic",
    "181_Electrical_small": "Electronics",
    "182_Electrical_large": "Electronics",
    "211_Food_leftover": "Organic",
    "212_Food_other": "Organic",
    "3111_Hazardous_other": "Unknown plastic",
    "3112_Hazardous_medical": "Unknown plastic",
    "312_Hazardous_light": "Electronics",
    "313_Hazardous_battery": "Battery",
    "321_Bulky_wood": "Wood",
    "331_Other_house_organic": "Organic",
    "333_Other_household": "Unknown plastic",
    "334_Other_plastic": "Unknown plastic",
}

GARBAGE_CLASSIFICATION_V2_CLASS_MAP = {
    "battery": "Battery",
    "biological": "Organic",
    "brown-glass": "Glass bottle",
    "brown_glass": "Glass bottle",
    "cardboard": "Cardboard",
    "clothes": "Textile",
    "green-glass": "Glass bottle",
    "green_glass": "Glass bottle",
    "glass": "Glass bottle",
    "metal": "Scrap metal",
    "paper": "Paper",
    "plastic": "Combined plastic",
    "shoes": "Textile",
    "trash": "Unknown plastic",
    "white-glass": "Glass bottle",
    "white_glass": "Glass bottle",
}


@dataclass(frozen=True)
class KaggleClassificationRow:
    source_dataset: str
    source_name: str
    source_path: str
    original_split: str
    classifier_split: str
    source_class: str
    canonical_class: str
    bin_code: str
    bin_name: str
    bin_index: int
    bbox_status: str = "missing"
    yolo_trainable: bool = False


def iter_classification_rows(dataset_root: Path, source_dataset: str) -> Iterator[KaggleClassificationRow]:
    if source_dataset == VN_TRASH_CLASSIFICATION_REF:
        yield from _iter_vn_trash_rows(dataset_root)
    elif source_dataset == DOMESTIC_SOLID_WASTE_REF:
        yield from _iter_domestic_rows(dataset_root)
    elif source_dataset == GARBAGE_CLASSIFICATION_V2_REF:
        yield from _iter_garbage_classification_v2_rows(dataset_root)
    else:
        raise ValueError(f"unsupported classification dataset: {source_dataset}")


def write_manifest(rows: Iterable[KaggleClassificationRow], out_jsonl: Path, summary_path: Path) -> dict:
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    total = 0
    with out_jsonl.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            data = asdict(row)
            fh.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")
            counts[row.bin_code] += 1
            class_counts[row.canonical_class] += 1
            source_counts[row.source_dataset] += 1
            split_counts[row.classifier_split] += 1
            total += 1
    summary = {
        "manifest": str(out_jsonl),
        "images": total,
        "by_bin": dict(sorted(counts.items())),
        "by_class": dict(sorted(class_counts.items())),
        "by_source_dataset": dict(sorted(source_counts.items())),
        "by_classifier_split": dict(sorted(split_counts.items())),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def read_manifest(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                yield value


def classifier_split_for_path(path: Path, original_split: str) -> str:
    clean = original_split.strip().casefold()
    if clean == "test":
        return "test"
    if clean in {"valid", "val"}:
        return "valid"
    if clean == "train":
        return "train"
    digest = int(hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8], 16) % 10
    if digest == 0:
        return "test"
    if digest == 1:
        return "valid"
    return "train"


def route_for_canonical_class(class_name: str) -> WasteCategory:
    return category_for_class(canonical_class_name(class_name))


def _iter_vn_trash_rows(root: Path) -> Iterator[KaggleClassificationRow]:
    base = root / "VN_trash_classification"
    if not base.exists():
        base = root
    for image_path in _image_files(base):
        rel = image_path.relative_to(base)
        if len(rel.parts) < 3:
            continue
        original_split = rel.parts[0]
        source_class = rel.parts[1]
        canonical = VN_TRASH_CLASS_MAP.get(source_class)
        if canonical is None:
            continue
        yield _row(
            image_path,
            source_dataset=VN_TRASH_CLASSIFICATION_REF,
            source_name=KAGGLE_VN_TRASH_CLASSIFICATION_SOURCE,
            original_split=original_split,
            source_class=source_class,
            canonical_class=canonical,
        )


def _iter_domestic_rows(root: Path) -> Iterator[KaggleClassificationRow]:
    for image_path in _image_files(root):
        rel = image_path.relative_to(root)
        if len(rel.parts) < 2:
            continue
        source_class = rel.parts[0]
        canonical = DOMESTIC_SOLID_WASTE_CLASS_MAP.get(source_class)
        if canonical is None:
            continue
        yield _row(
            image_path,
            source_dataset=DOMESTIC_SOLID_WASTE_REF,
            source_name=KAGGLE_DOMESTIC_SOLID_WASTE_SOURCE,
            original_split="unknown",
            source_class=source_class,
            canonical_class=canonical,
        )


def _iter_garbage_classification_v2_rows(root: Path) -> Iterator[KaggleClassificationRow]:
    base = root / "garbage-dataset"
    if not base.exists():
        base = root / "Garbage classification"
    if not base.exists():
        base = root
    for image_path in _image_files(base):
        rel = image_path.relative_to(base)
        if len(rel.parts) < 2:
            continue
        source_class = rel.parts[-2]
        canonical = GARBAGE_CLASSIFICATION_V2_CLASS_MAP.get(_normalize_source_label(source_class))
        if canonical is None:
            continue
        yield _row(
            image_path,
            source_dataset=GARBAGE_CLASSIFICATION_V2_REF,
            source_name=KAGGLE_GARBAGE_CLASSIFICATION_V2_SOURCE,
            original_split=_split_from_parts(rel.parts),
            source_class=source_class,
            canonical_class=canonical,
        )


def _row(
    image_path: Path,
    *,
    source_dataset: str,
    source_name: str,
    original_split: str,
    source_class: str,
    canonical_class: str,
) -> KaggleClassificationRow:
    canonical = canonical_class_name(canonical_class)
    route = route_for_canonical_class(canonical)
    return KaggleClassificationRow(
        source_dataset=source_dataset,
        source_name=source_name,
        source_path=str(image_path),
        original_split=original_split,
        classifier_split=classifier_split_for_path(image_path, original_split),
        source_class=source_class,
        canonical_class=canonical,
        bin_code=route.code,
        bin_name=route.name,
        bin_index=route.bin_index,
    )


def _image_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    yield from sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTS)


def _normalize_source_label(value: str) -> str:
    return value.strip().casefold().replace(" ", "-")


def _split_from_parts(parts: tuple[str, ...]) -> str:
    for part in parts[:-1]:
        clean = part.strip().casefold()
        if clean in {"train", "valid", "val", "test"}:
            return clean
    return "unknown"


__all__ = [
    "DOMESTIC_SOLID_WASTE_CLASS_MAP",
    "DOMESTIC_SOLID_WASTE_REF",
    "GARBAGE_CLASSIFICATION_V2_CLASS_MAP",
    "GARBAGE_CLASSIFICATION_V2_REF",
    "IMAGE_EXTS",
    "VN_TRASH_CLASSIFICATION_REF",
    "VN_TRASH_CLASS_MAP",
    "KaggleClassificationRow",
    "classifier_split_for_path",
    "iter_classification_rows",
    "read_manifest",
    "route_for_canonical_class",
    "write_manifest",
]
