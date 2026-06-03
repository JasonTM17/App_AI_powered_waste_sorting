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
from app.core.dataset_trust import DatasetTrustState, classify_dataset_item
from app.core.licensed_source_ingestion import GENERATED_CAP_RATIO
from app.core.training_source_flags import is_generated_meta, is_train_only_supplemental_meta
from app.core.waste_categories import canonical_class_name


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
    min_box_area: float = 0.0,
    min_box_side: float = 0.0,
    require_reviewed: bool = False,
    generated_cap_ratio: float = GENERATED_CAP_RATIO,
    seed: int = 42,
) -> dict[str, object]:
    blocked_labels: Counter[str] = Counter()
    blocked_items: Counter[str] = Counter()
    items = _load_items(
        queue_dir,
        set(class_names),
        blocked_labels=blocked_labels,
        blocked_items=blocked_items,
        require_reviewed=require_reviewed,
    )
    selected = _select_items(
        items,
        max_images=max_images,
        legacy_quota=legacy_quota,
        focus_classes=set(focus_classes),
        generated_cap_ratio=generated_cap_ratio,
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
        "min_box_area": min_box_area,
        "min_box_side": min_box_side,
        "require_reviewed": require_reviewed,
        "generated_cap_ratio": generated_cap_ratio,
        "skipped_small_boxes": 0,
        "skipped_unknown_boxes": 0,
        "blocked_labels": blocked_labels,
        "blocked_items": blocked_items,
    }
    for item in selected:
        split = _split_for(item)
        lines = _label_lines(
            item,
            class_ids,
            stats,
            min_box_area=min_box_area,
            min_box_side=min_box_side,
        )
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


def _load_items(
    queue_dir: Path,
    allowed: set[str],
    *,
    blocked_labels: Counter[str],
    blocked_items: Counter[str],
    require_reviewed: bool,
) -> list[QueueItem]:
    items: list[QueueItem] = []
    for image_path in queue_dir.glob("*.jpg"):
        try:
            meta = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
        except Exception:
            blocked_items["invalid_json"] += 1
            continue
        if not isinstance(meta, dict):
            blocked_items["invalid_meta"] += 1
            continue
        decision = classify_dataset_item(meta)
        class_names: set[str] = set()
        for box in meta.get("boxes") or []:
            raw_name = str(box.get("cls_name") or "").strip()
            class_name = canonical_class_name(raw_name)
            if class_name in allowed:
                class_names.add(class_name)
            elif raw_name:
                blocked_labels[raw_name] += 1
        if require_reviewed and (meta.get("reviewed") is not True or meta.get("bbox_reviewed") is not True):
            blocked_items["review_required"] += 1
            continue
        supplemental = is_train_only_supplemental_meta(meta)
        if not is_trainable_meta(meta) and decision.state is not DatasetTrustState.HOLDOUT and not supplemental:
            for reason in decision.reasons or (decision.state.value,):
                blocked_items[reason] += 1
            continue
        classes = frozenset(class_names)
        if classes:
            items.append(QueueItem(image_path, meta, classes))
        else:
            blocked_items["no_allowed_classes"] += 1
    return items


def _select_items(
    items: list[QueueItem],
    *,
    max_images: int,
    legacy_quota: int,
    focus_classes: set[str],
    generated_cap_ratio: float,
    seed: int,
) -> list[QueueItem]:
    rng = random.Random(seed)
    ordered = list(items)
    rng.shuffle(ordered)
    ordered.sort(key=lambda item: (not bool(item.classes & focus_classes), _is_generated(item.meta)))
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
        if _is_generated(item.meta) and not _within_generated_cap(
            item.classes,
            class_counts,
            generated_counts,
            generated_cap_ratio,
        ):
            continue
        selected.append(item)
        class_counts.update(item.classes)
        if _is_generated(item.meta):
            generated_counts.update(item.classes)
    return selected


def _label_lines(
    item: QueueItem,
    class_ids: dict[str, int],
    stats: dict[str, object],
    *,
    min_box_area: float,
    min_box_side: float,
) -> list[str]:
    try:
        with Image.open(item.image_path) as image:
            width, height = image.size
    except Exception:
        return []
    lines: list[str] = []
    for box in item.meta.get("boxes") or []:
        name = canonical_class_name(str(box.get("cls_name") or "").strip())
        if name not in class_ids:
            if name:
                stats["skipped_unknown_boxes"] = int(str(stats["skipped_unknown_boxes"])) + 1
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
        if (min_box_area > 0 and bw * bh < min_box_area) or (
            min_box_side > 0 and (bw < min_box_side or bh < min_box_side)
        ):
            stats["skipped_small_boxes"] = int(str(stats["skipped_small_boxes"])) + 1
            continue
        lines.append(f"{class_ids[name]} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        stats["classes"][name] += 1  # type: ignore[index]
    return lines


def _split_for(item: QueueItem) -> str:
    if is_train_only_supplemental_meta(item.meta):
        return "train"
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
    return is_generated_meta(meta)


def _within_generated_cap(
    classes: frozenset[str],
    class_counts: Counter[str],
    generated_counts: Counter[str],
    generated_cap_ratio: float,
) -> bool:
    if generated_cap_ratio <= 0:
        return False
    real_ratio = generated_cap_ratio / max(0.01, 1.0 - generated_cap_ratio)
    for name in classes:
        real_count = class_counts[name] - generated_counts[name]
        if real_count <= 0:
            return False
        cap = max(1, int(real_count * real_ratio))
        if generated_counts[name] >= cap:
            return False
    return True


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
