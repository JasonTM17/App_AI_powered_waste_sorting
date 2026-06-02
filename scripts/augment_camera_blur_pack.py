"""Create train-only camera-blur augmentation samples from reviewed data."""

from __future__ import annotations

import argparse
import json
import random
import sys
import uuid
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_catalog import DatasetCatalog  # noqa: E402
from app.core.dataset_queue import is_trainable_meta  # noqa: E402
from app.core.training_source_flags import is_train_only_supplemental_meta  # noqa: E402
from app.core.vietnam_waste_targets import P0_CLASSES  # noqa: E402
from app.core.waste_categories import TRAINING_CLASS_ORDER_45, canonical_class_name  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--catalog", type=Path, default=Path("dataset_v2/dataset.db"))
    parser.add_argument("--class-name", action="append", default=[])
    parser.add_argument("--variants", type=int, default=2)
    parser.add_argument("--max-per-class", type=int, default=48)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    targets = set(args.class_name or P0_CLASSES)
    created = _augment_queue(args.queue, args.catalog, targets, args.variants, args.max_per_class, rng)
    report = {"created": created, "targets": sorted(targets)}
    report_path = args.queue.parent / "camera_blur_augmentation_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Created {created} camera-blur augmentation image(s).")
    print(f"Report: {report_path}")
    return 0


def _augment_queue(
    queue_dir: Path,
    catalog_path: Path,
    targets: set[str],
    variants: int,
    max_per_class: int,
    rng: random.Random,
) -> int:
    queue_dir.mkdir(parents=True, exist_ok=True)
    created_by_class = {name: 0 for name in targets}
    catalog = DatasetCatalog(catalog_path)
    created = 0
    try:
        for image_path in sorted(queue_dir.glob("*.jpg")):
            meta = _read_meta(image_path.with_suffix(".json"))
            classes = _classes(meta) & targets
            if not classes or not _can_augment(meta):
                continue
            class_name = sorted(classes)[0]
            for _ in range(variants):
                if created_by_class[class_name] >= max_per_class:
                    break
                out_path, out_meta = _write_augmented(image_path, meta, class_name, rng)
                catalog.upsert_item(out_path, out_meta)
                created_by_class[class_name] += 1
                created += 1
        return created
    finally:
        catalog.close()


def _can_augment(meta: dict) -> bool:
    holdout = meta.get("holdout") is True or str(meta.get("split") or "").lower() == "test"
    return (
        meta.get("reviewed") is True
        and meta.get("bbox_reviewed") is True
        and is_trainable_meta(meta)
        and not holdout
        and not is_train_only_supplemental_meta(meta)
    )


def _write_augmented(
    image_path: Path,
    meta: dict,
    class_name: str,
    rng: random.Random,
) -> tuple[Path, dict]:
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        augmented = _camera_blur(rgb, rng)
    uid = uuid.uuid4().hex[:12]
    out_path = image_path.parent / f"camera_blur_{uid}.jpg"
    augmented.save(out_path, format="JPEG", quality=90)
    out_meta = json.loads(json.dumps(meta))
    out_meta.update(
        {
            "ts": datetime.now().isoformat(),
            "source": "camera_blur_augmented",
            "source_type": "camera_blur_augmented",
            "camera_blur_augmented": True,
            "augmentation_parent": str(image_path),
            "augmentation_profile": "blur_downscale_noise_contrast_v1",
            "canonical_class": class_name,
            "generated": False,
            "recognition_enabled": False,
            "reviewed": True,
            "bbox_reviewed": True,
            "needs_annotation": False,
            "split": "train",
            "split_lock": True,
            "holdout": False,
        }
    )
    out_path.with_suffix(".json").write_text(json.dumps(out_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path, out_meta


def _camera_blur(image: Image.Image, rng: random.Random) -> Image.Image:
    width, height = image.size
    scale = rng.uniform(0.45, 0.72)
    small = image.resize((max(8, int(width * scale)), max(8, int(height * scale))), Image.Resampling.BILINEAR)
    out = small.resize((width, height), Image.Resampling.BILINEAR)
    out = out.filter(ImageFilter.GaussianBlur(rng.uniform(0.4, 1.25)))
    out = ImageEnhance.Contrast(out).enhance(rng.uniform(0.72, 0.95))
    out = ImageEnhance.Brightness(out).enhance(rng.uniform(0.88, 1.08))
    noise = Image.effect_noise((width, height), rng.uniform(2.0, 7.0)).convert("RGB")
    return Image.blend(out, noise, rng.uniform(0.015, 0.045))


def _classes(meta: dict) -> set[str]:
    allowed = set(TRAINING_CLASS_ORDER_45)
    names: set[str] = set()
    for box in meta.get("boxes") or []:
        if isinstance(box, dict):
            class_name = canonical_class_name(str(box.get("cls_name") or ""))
            if class_name in allowed:
                names.add(class_name)
    return names


def _read_meta(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
