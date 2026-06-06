"""Balanced, group-aware YOLO export used by the fast Pen fine-tune."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.core.dataset_queue import is_trainable_meta


@dataclass(frozen=True)
class QueueItem:
    image_path: Path
    meta: dict
    classes: frozenset[str]


def export_balanced_trainset(
    queue_dir: Path,
    out_dir: Path,
    class_names: tuple[str, ...],
    *,
    max_images: int = 4500,
    legacy_quota: int = 75,
    focus_classes: tuple[str, ...] = ("Pen", "Battery", "Toothbrush"),
    seed: int = 42,
) -> dict[str, object]:
    items = _load_items(queue_dir, set(class_names))
    selected = _select_items(
        items,
        max_images=max_images,
        legacy_quota=legacy_quota,
        focus_classes=set(focus_classes),
        seed=seed,
    )
    _reset_output(out_dir)
    class_ids = {name: index for index, name in enumerate(class_names)}
    stats: dict[str, object] = {
        "images": 0,
        "boxes": 0,
        "splits": Counter(),
        "classes": Counter(),
        "sources": Counter(),
        "focus_classes": list(focus_classes),
        "max_images": max_images,
        "legacy_quota": legacy_quota,
    }
    for item in selected:
        split = _split_for(item)
        lines = _label_lines(item, class_ids, stats)
        if not lines:
            continue
        image_out = out_dir / "images" / split / item.image_path.name
        label_out = out_dir / "labels" / split / f"{item.image_path.stem}.txt"
        image_out.parent.mkdir(parents=True, exist_ok=True)
        label_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.image_path, image_out)
        label_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        stats["images"] = int(str(stats["images"])) + 1
        stats["boxes"] = int(str(stats["boxes"])) + len(lines)
        stats["splits"][split] += 1  # type: ignore[index]
        stats["sources"][str(item.meta.get("source") or "unknown")] += 1  # type: ignore[index]
    _write_data_yaml(out_dir, class_names)
    return _jsonable(stats)


def _load_items(queue_dir: Path, allowed: set[str]) -> list[QueueItem]:
    items: list[QueueItem] = []
    for image_path in queue_dir.glob("*.jpg"):
        try:
            meta = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(meta, dict) or not is_trainable_meta(meta):
            continue
        classes = frozenset(
            str(box.get("cls_name") or "").strip()
            for box in meta.get("boxes") or []
            if str(box.get("cls_name") or "").strip() in allowed
        )
        if classes:
            items.append(QueueItem(image_path, meta, classes))
    return items


def _select_items(
    items: list[QueueItem],
    *,
    max_images: int,
    legacy_quota: int,
    focus_classes: set[str],
    seed: int,
) -> list[QueueItem]:
    rng = random.Random(seed)
    ordered = list(items)
    rng.shuffle(ordered)
    ordered.sort(key=lambda item: not bool(item.classes & focus_classes))
    selected: list[QueueItem] = []
    class_counts: Counter[str] = Counter()
    generated_counts: Counter[str] = Counter()
    for item in ordered:
        if len(selected) >= max_images:
            break
        focus = item.classes & focus_classes
        needed_legacy = any(class_counts[name] < legacy_quota for name in item.classes)
        if not focus and not needed_legacy:
            continue
        if _is_generated(item.meta) and any(
            generated_counts[name] >= max(1, class_counts[name] // 4)
            for name in item.classes
        ):
            continue
        selected.append(item)
        class_counts.update(item.classes)
        if _is_generated(item.meta):
            generated_counts.update(item.classes)
    return selected


def _label_lines(item: QueueItem, class_ids: dict[str, int], stats: dict[str, object]) -> list[str]:
    try:
        with Image.open(item.image_path) as image:
            width, height = image.size
    except Exception:
        return []
    lines: list[str] = []
    for box in item.meta.get("boxes") or []:
        name = str(box.get("cls_name") or "").strip()
        if name not in class_ids:
            continue
        xyxy = box.get("xyxy") or []
        if len(xyxy) < 4:
            continue
        x1, y1, x2, y2 = (float(value) for value in xyxy[:4])
        cx = ((x1 + x2) / 2) / max(1, width)
        cy = ((y1 + y2) / 2) / max(1, height)
        bw = max(0.0, x2 - x1) / max(1, width)
        bh = max(0.0, y2 - y1) / max(1, height)
        if bw <= 0 or bh <= 0:
            continue
        lines.append(f"{class_ids[name]} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        stats["classes"][name] += 1  # type: ignore[index]
    return lines


def _split_for(item: QueueItem) -> str:
    if item.meta.get("split_lock"):
        split = str(item.meta.get("split") or "train").lower()
        return "valid" if split == "val" else split if split in {"train", "valid", "test"} else "train"
    group = str(
        item.meta.get("capture_session_id")
        or item.meta.get("group_id")
        or item.meta.get("original_file")
        or item.image_path.stem
    )
    bucket = int(hashlib.sha1(group.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "train" if bucket < 0.8 else "valid" if bucket < 0.9 else "test"


def _is_generated(meta: dict) -> bool:
    source = str(meta.get("source") or "").lower()
    return source.startswith(("generated", "synthetic", "imagegen"))


def _reset_output(out_dir: Path) -> None:
    for name in ("images", "labels"):
        target = out_dir / name
        if target.exists():
            shutil.rmtree(target)
    out_dir.mkdir(parents=True, exist_ok=True)


def _write_data_yaml(out_dir: Path, names: tuple[str, ...]) -> None:
    rows = "\n".join(f"  {index}: {name}" for index, name in enumerate(names))
    (out_dir / "data.yaml").write_text(
        f"path: {out_dir.resolve().as_posix()}\n"
        "train: images/train\nval: images/valid\ntest: images/test\n"
        f"nc: {len(names)}\nnames:\n{rows}\n",
        encoding="utf-8",
    )


def _jsonable(stats: dict[str, object]) -> dict[str, object]:
    return {
        key: dict(value) if isinstance(value, Counter) else value
        for key, value in stats.items()
    }


__all__ = ["export_balanced_trainset"]
