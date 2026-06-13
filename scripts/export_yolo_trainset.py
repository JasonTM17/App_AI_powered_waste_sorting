"""Export the reviewed queue to a YOLO train/valid/test folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_queue import is_trainable_meta  # noqa: E402
from app.core.waste_categories import (  # noqa: E402
    TRAINING_CLASS_ORDER_45,
    canonical_class_name,
    category_for_class,
)


@dataclass(frozen=True)
class ExportEntry:
    image_path: Path
    meta: dict[str, Any]
    width: int
    height: int
    image_hash: str
    group_key: str
    locked_split: str | None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2") / "low_conf_queue")
    parser.add_argument("--out", type=Path, default=Path("dataset_v2") / "yolo_trainset")
    parser.add_argument("--model", type=Path, default=Path("models") / "best.pt")
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--valid-ratio", type=float, default=0.1)
    args = parser.parse_args()

    class_names = _model_classes(args.model)
    args.out.mkdir(parents=True, exist_ok=True)
    stats = _export_queue(
        args.queue,
        args.out,
        class_names,
        train_ratio=args.train_ratio,
        valid_ratio=args.valid_ratio,
    )
    (args.out / "export_report.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Exported {stats['images']} images and {stats['boxes']} boxes to {args.out}")
    print(f"Skipped untrusted: {stats['skipped_untrusted']}")
    print(f"data.yaml: {args.out / 'data.yaml'}")
    return 0


def _export_queue(
    queue_dir: Path,
    out_dir: Path,
    class_names: dict[int, str],
    *,
    train_ratio: float,
    valid_ratio: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    input_class_names = dict(class_names)
    class_names = _canonical_training_class_names()
    stats: dict[str, Any] = {
        "images": 0,
        "boxes": 0,
        "class_count": len(class_names),
        "class_map_source": "canonical_training_class_order_45",
        "input_model_class_count": len(input_class_names),
        "model_class_mismatches": _class_map_mismatches(input_class_names, class_names),
        "splits": {"train": 0, "valid": 0, "test": 0},
        "classes": {},
        "skipped_untrusted": 0,
        "skipped_missing_meta": 0,
        "skipped_empty": 0,
        "skipped_empty_after_filter": 0,
        "skipped_unknown_boxes": 0,
        "skipped_invalid_bbox": 0,
        "remapped_boxes": 0,
        "duplicate_image_groups": 0,
        "duplicate_image_files": 0,
        "split_locked_groups": 0,
        "route_boxes": {"O": 0, "R": 0, "I": 0},
        "split_route_boxes": {
            "train": {"O": 0, "R": 0, "I": 0},
            "valid": {"O": 0, "R": 0, "I": 0},
            "test": {"O": 0, "R": 0, "I": 0},
        },
    }
    _reset_export_output(out_dir)
    if not queue_dir.exists():
        _write_data_yaml(out_dir, class_names)
        return stats

    class_id_by_name = {name: cls_id for cls_id, name in class_names.items()}
    entries = _collect_export_entries(queue_dir, stats)
    split_by_group = _assign_group_splits(
        entries,
        train_ratio=train_ratio,
        valid_ratio=valid_ratio,
    )
    group_counts: dict[str, int] = {}
    for entry in entries:
        group_counts[entry.group_key] = group_counts.get(entry.group_key, 0) + 1
    duplicate_counts = [count for count in group_counts.values() if count > 1]
    stats["duplicate_image_groups"] = len(duplicate_counts)
    stats["duplicate_image_files"] = sum(duplicate_counts)
    stats["split_locked_groups"] = len(
        {entry.group_key for entry in entries if entry.locked_split is not None}
    )

    for entry in entries:
        image_path = entry.image_path
        meta = entry.meta
        width = entry.width
        height = entry.height
        boxes = list(meta.get("boxes") or [])
        split = split_by_group[entry.group_key]
        lines = []
        for box in boxes:
            xyxy = box.get("xyxy") or [0, 0, 1, 1]
            if not _valid_bbox(xyxy, width, height):
                stats["skipped_invalid_bbox"] += 1
                continue
            cls_id = int(box.get("cls_id", 0))
            cls_name = canonical_class_name(
                str(box.get("cls_name") or class_names.get(cls_id, str(cls_id)))
            )
            expected_id = class_id_by_name.get(cls_name)
            if expected_id is not None:
                if expected_id != cls_id:
                    stats["remapped_boxes"] += 1
                cls_id = expected_id
            elif cls_id not in class_names:
                stats["skipped_unknown_boxes"] += 1
                continue
            cls_name = class_names[cls_id]
            stats["classes"][cls_name] = int(stats["classes"].get(cls_name, 0)) + 1
            route = category_for_class(cls_name).code
            stats["route_boxes"][route] = int(stats["route_boxes"].get(route, 0)) + 1
            stats["split_route_boxes"][split][route] = (
                int(stats["split_route_boxes"][split].get(route, 0)) + 1
            )
            lines.append(_box_to_yolo_line(cls_id, xyxy, width, height))
        if not lines:
            stats["skipped_empty_after_filter"] += 1
            continue
        image_out = out_dir / "images" / split / image_path.name
        label_out = out_dir / "labels" / split / f"{image_path.stem}.txt"
        image_out.parent.mkdir(parents=True, exist_ok=True)
        label_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image_path, image_out)
        label_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        stats["images"] += 1
        stats["boxes"] += len(lines)
        stats["splits"][split] += 1
    _write_data_yaml(out_dir, class_names)
    return stats


def _collect_export_entries(queue_dir: Path, stats: dict[str, Any]) -> list[ExportEntry]:
    entries: list[ExportEntry] = []
    for image_path in sorted(queue_dir.glob("*.jpg")):
        meta = _read_meta(image_path)
        if meta is None:
            stats["skipped_missing_meta"] += 1
            continue
        if not is_trainable_meta(meta):
            stats["skipped_untrusted"] += 1
            continue
        boxes = list(meta.get("boxes") or [])
        if not boxes:
            stats["skipped_empty"] += 1
            continue
        try:
            with Image.open(image_path) as image:
                width, height = image.size
        except Exception:
            stats["skipped_empty"] += 1
            continue
        image_hash = _sha256_file(image_path)
        entries.append(
            ExportEntry(
                image_path=image_path,
                meta=meta,
                width=width,
                height=height,
                image_hash=image_hash,
                group_key=_split_group_key(image_path, meta, image_hash),
                locked_split=_locked_split(meta),
            )
        )
    return entries


def _assign_group_splits(
    entries: list[ExportEntry],
    *,
    train_ratio: float,
    valid_ratio: float,
) -> dict[str, str]:
    locked_by_group: dict[str, set[str]] = {}
    for entry in entries:
        if entry.locked_split is not None:
            locked_by_group.setdefault(entry.group_key, set()).add(entry.locked_split)

    split_by_group: dict[str, str] = {}
    for entry in entries:
        if entry.group_key in split_by_group:
            continue
        locked = locked_by_group.get(entry.group_key, set())
        if "test" in locked:
            split = "test"
        elif "valid" in locked:
            split = "valid"
        elif "train" in locked:
            split = "train"
        else:
            split = _stable_split(entry.group_key, train_ratio, valid_ratio)
        split_by_group[entry.group_key] = split
    return split_by_group


def _split_group_key(image_path: Path, meta: dict[str, Any], image_hash: str) -> str:
    if image_hash:
        return f"sha256:{image_hash}"
    for key in (
        "capture_session_id",
        "source_path",
        "original_file",
        "perceptual_hash",
    ):
        value = str(meta.get(key) or "").strip()
        if value:
            return f"{key}:{value.casefold()}"
    return f"sha256:{image_hash}"


def _locked_split(meta: dict[str, Any]) -> str | None:
    if meta.get("holdout") is True:
        return "test"
    raw = str(meta.get("split") or "").strip().lower()
    if raw == "val":
        raw = "valid"
    if meta.get("split_lock") is True and raw in {"train", "valid", "test"}:
        return raw
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_bbox(xyxy: object, width: int, height: int) -> bool:
    if not isinstance(xyxy, list | tuple) or len(xyxy) < 4:
        return False
    try:
        x1, y1, x2, y2 = (float(value) for value in xyxy[:4])
    except (TypeError, ValueError):
        return False
    return x1 >= 0 and y1 >= 0 and x2 > x1 and y2 > y1 and x2 <= width and y2 <= height


def _reset_export_output(out_dir: Path) -> None:
    for name in ("images", "labels"):
        target = out_dir / name
        if target.exists():
            shutil.rmtree(target)
    for cache_file in out_dir.glob("*.cache"):
        with suppress(OSError):
            cache_file.unlink()


def _canonical_training_class_names() -> dict[int, str]:
    return {idx: name for idx, name in enumerate(TRAINING_CLASS_ORDER_45)}


def _class_map_mismatches(
    input_class_names: dict[int, str],
    canonical_class_names: dict[int, str],
) -> list[dict[str, Any]]:
    if not input_class_names:
        return []
    mismatches: list[dict[str, Any]] = []
    for idx, expected in canonical_class_names.items():
        actual = input_class_names.get(idx)
        if actual is not None and actual != expected:
            mismatches.append({"cls_id": idx, "model": actual, "canonical": expected})
    for idx, actual in input_class_names.items():
        if idx not in canonical_class_names:
            mismatches.append({"cls_id": idx, "model": actual, "canonical": None})
    return mismatches


def _class_names_with_allowed_queue_extras(
    queue_dir: Path,
    class_names: dict[int, str],
    *,
    allowed_names: tuple[str, ...],
) -> dict[int, str]:
    out = dict(class_names)
    used_names = {name for name in out.values()}
    allowed_set = set(allowed_names)
    present_extras: set[str] = set()
    for image_path in sorted(queue_dir.glob("*.jpg")):
        meta = _read_meta(image_path)
        if meta is None or not is_trainable_meta(meta):
            continue
        for box in meta.get("boxes") or []:
            cls_name = canonical_class_name(str(box.get("cls_name") or ""))
            if cls_name and cls_name not in used_names and cls_name in allowed_set:
                present_extras.add(cls_name)
    next_id = max(out.keys(), default=-1) + 1
    for cls_name in allowed_names:
        if cls_name not in present_extras or cls_name in used_names:
            continue
        out[next_id] = cls_name
        used_names.add(cls_name)
        next_id += 1
    return out


def _read_meta(image_path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _box_to_yolo_line(cls_id: int, xyxy: list[float], width: int, height: int) -> str:
    x1, y1, x2, y2 = (float(v) for v in xyxy[:4])
    cx = ((x1 + x2) / 2) / max(width, 1)
    cy = ((y1 + y2) / 2) / max(height, 1)
    bw = max(0.0, x2 - x1) / max(width, 1)
    bh = max(0.0, y2 - y1) / max(height, 1)
    return f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"


def _stable_split(stem: str, train_ratio: float, valid_ratio: float) -> str:
    bucket = int(hashlib.sha1(stem.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    if bucket < train_ratio:
        return "train"
    if bucket < train_ratio + valid_ratio:
        return "valid"
    return "test"


def _model_classes(model_path: Path) -> dict[int, str]:
    if not model_path.exists():
        return {}
    try:
        from ultralytics import YOLO

        return {int(k): str(v) for k, v in dict(YOLO(str(model_path)).names).items()}
    except Exception as e:
        print(f"Warning: could not inspect model classes: {e}")
        return {}


def _write_data_yaml(out_dir: Path, class_names: dict[int, str]) -> None:
    if not class_names:
        ordered: list[tuple[int, str]] = []
    else:
        max_id = max(class_names)
        ordered = [(idx, class_names.get(idx, str(idx))) for idx in range(max_id + 1)]
    names = "\n".join(f"  {idx}: {name}" for idx, name in ordered)
    yaml = (
        f"path: {out_dir.resolve().as_posix()}\n"
        "train: images/train\n"
        "val: images/valid\n"
        "test: images/test\n"
        f"nc: {len(ordered)}\n"
        "names:\n"
        f"{names}\n"
    )
    (out_dir / "data.yaml").write_text(yaml, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
