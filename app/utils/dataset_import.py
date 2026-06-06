"""Dataset import helpers for YOLO/Roboflow exports."""

from __future__ import annotations

import ast
import json
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

LABEL_MAP_PRESETS: dict[str, dict[str, str]] = {
    "waste_detection_2": {
        "Bottle": "Plastic bottle",
        "Can": "Aluminum can",
        "Carton": "Cardboard",
        "E-Waste": "Electronics",
        "Electric Cable": "Electronics",
        "Glass": "Glass bottle",
        "Glass Bottle": "Glass bottle",
        "Metal": "Scrap metal",
        "Organic Waste": "Organic",
        "Phone Case": "Unknown plastic",
        "Plastics": "Unknown plastic",
        "Spoon": "Iron utensils",
        "Wooden Waste": "Wood",
        "paper": "Paper",
    },
    "pen_hardware_downloads": {
        "Pen": "Pen",
        "pen": "Pen",
        "PEN": "Pen",
        "battery": "Battery",
        "Battery": "Battery",
        "toothbrushes": "Toothbrush",
        "Toothbrushes": "Toothbrush",
        "toothbrush": "Toothbrush",
        "aluminum-cans": "Aluminum can",
        "aluminum-can": "Aluminum can",
        "Aluminum cans": "Aluminum can",
        "BIODEGRADABLE": "Organic",
        "Biodegradable": "Organic",
        "CARDBOARD": "Cardboard",
        "Cardboard": "Cardboard",
        "PAPER": "Paper",
        "paper": "Paper",
        "Paper": "Paper",
    },
}


def label_map_for_preset(preset: str) -> dict[str, str] | None:
    if preset == "none":
        return None
    value = LABEL_MAP_PRESETS.get(preset)
    return dict(value) if value is not None else None


def import_yolo_dataset_to_queue(
    dataset_path: Path,
    queue_dir: Path,
    *,
    source_name: str = "yolo_import",
    limit: int | None = None,
    catalog_path: Path | None = None,
    class_name_to_id: dict[str, int] | None = None,
    label_map: dict[str, str] | None = None,
) -> int:
    """Convert a YOLO detection dataset folder/zip into queue image+json items."""
    from app.core.dataset_catalog import DatasetCatalog

    catalog = DatasetCatalog(catalog_path) if catalog_path is not None else None
    root, cleanup = _dataset_root(dataset_path)
    try:
        names = _read_yolo_names(root / "data.yaml")
        dataset_metadata = _read_dataset_metadata(root / "data.yaml")
        pairs = _find_yolo_pairs(root)
        queue_dir.mkdir(parents=True, exist_ok=True)
        imported = 0
        for image_path, label_path, split in pairs:
            if limit is not None and imported >= limit:
                break
            boxes = _read_yolo_boxes(
                image_path,
                label_path,
                names,
                class_name_to_id=class_name_to_id,
                label_map=label_map,
            )
            if not boxes:
                continue
            unknown_labels = sorted(
                {
                    str(box.get("original_cls_name") or box.get("cls_name") or "")
                    for box in boxes
                    if box.get("unknown_label")
                }
            )
            item_source = "untrusted" if unknown_labels else source_name
            try:
                with Image.open(image_path) as im:
                    rgb = im.convert("RGB")
                    uid = uuid.uuid4().hex[:12]
                    out_img = queue_dir / f"{item_source}_{uid}.jpg"
                    rgb.save(out_img, format="JPEG", quality=92)
            except Exception:
                continue
            meta = {
                "ts": datetime.now().isoformat(),
                "source": item_source,
                "split": split,
                "original_file": str(image_path),
                "boxes": boxes,
            }
            meta.update(dataset_metadata)
            if unknown_labels:
                meta["intended_source"] = source_name
                meta["unknown_labels"] = unknown_labels
            out_img.with_suffix(".json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            if catalog is not None:
                catalog.upsert_item(out_img, meta)
            imported += 1
        return imported
    finally:
        if catalog is not None:
            catalog.close()
        if cleanup is not None:
            shutil.rmtree(cleanup, ignore_errors=True)


def _dataset_root(dataset_path: Path) -> tuple[Path, Path | None]:
    if dataset_path.is_file() and dataset_path.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="trash_sorter_yolo_"))
        with zipfile.ZipFile(dataset_path) as zf:
            zf.extractall(tmp)
        candidates = [p for p in tmp.rglob("data.yaml")]
        if candidates:
            return candidates[0].parent, tmp
        return tmp, tmp
    return dataset_path, None


def _read_yolo_names(yaml_path: Path) -> dict[int, str]:
    if not yaml_path.exists():
        return {}
    text = yaml_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("names:"):
            value = stripped.removeprefix("names:").strip()
            if value:
                try:
                    parsed = ast.literal_eval(value)
                    return _normalize_names(parsed)
                except Exception:
                    return {}
            break
    names: dict[int, str] = {}
    in_names = False
    next_idx = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("names:"):
            in_names = True
            continue
        if not in_names:
            continue
        if not line.startswith((" ", "\t", "-")):
            break
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            try:
                names[int(key.strip())] = value.strip().strip("'\"")
            except ValueError:
                continue
        elif stripped.startswith("-"):
            names[next_idx] = stripped[1:].strip().strip("'\"")
            next_idx += 1
    return names


def _normalize_names(value) -> dict[int, str]:
    if isinstance(value, dict):
        return {int(k): str(v) for k, v in value.items()}
    if isinstance(value, list):
        return {i: str(v) for i, v in enumerate(value)}
    return {}


def _read_dataset_metadata(yaml_path: Path) -> dict[str, str | int]:
    if not yaml_path.exists():
        return {}
    text = yaml_path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, str | int] = {}
    in_roboflow = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "roboflow:":
            in_roboflow = True
            continue
        if in_roboflow and not line.startswith((" ", "\t")):
            in_roboflow = False
        if not in_roboflow or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if not key or not value:
            continue
        meta_key = {
            "workspace": "source_workspace",
            "project": "source_project",
            "version": "source_version",
            "license": "source_license",
            "url": "source_url",
        }.get(key)
        if meta_key is None:
            continue
        if key == "version":
            try:
                out[meta_key] = int(value)
                continue
            except ValueError:
                pass
        out[meta_key] = value
    return out


def _find_yolo_pairs(root: Path) -> list[tuple[Path, Path, str]]:
    pairs: list[tuple[Path, Path, str]] = []
    for image_path in sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXTS):
        if "images" not in [part.lower() for part in image_path.parts]:
            continue
        label_path = _label_for_image(root, image_path)
        if label_path is None or not label_path.exists():
            continue
        split = _split_for_image(root, image_path)
        pairs.append((image_path, label_path, split))
    return pairs


def _label_for_image(root: Path, image_path: Path) -> Path | None:
    rel = image_path.relative_to(root)
    parts = list(rel.parts)
    for i, part in enumerate(parts):
        if part.lower() == "images":
            parts[i] = "labels"
            return root.joinpath(*parts).with_suffix(".txt")
    return None


def _split_for_image(root: Path, image_path: Path) -> str:
    rel = image_path.relative_to(root)
    parts = [part.lower() for part in rel.parts]
    for split in ("train", "valid", "val", "test"):
        if split in parts:
            return "valid" if split == "val" else split
    return "unknown"


def _read_yolo_boxes(
    image_path: Path,
    label_path: Path,
    names: dict[int, str],
    *,
    class_name_to_id: dict[str, int] | None = None,
    label_map: dict[str, str] | None = None,
) -> list[dict]:
    try:
        with Image.open(image_path) as im:
            w, h = im.size
    except Exception:
        return []
    boxes: list[dict] = []
    for line in label_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        try:
            cls_id = int(float(parts[0]))
            cx, cy, bw, bh = (float(x) for x in parts[1:5])
        except ValueError:
            continue
        original_name = names.get(cls_id, str(cls_id)).strip()
        mapped_name = (label_map or {}).get(original_name, original_name).strip()
        unknown_label = class_name_to_id is not None and mapped_name not in class_name_to_id
        output_cls_id = class_name_to_id[mapped_name] if class_name_to_id and not unknown_label else cls_id
        x1 = max(0.0, (cx - bw / 2) * w)
        y1 = max(0.0, (cy - bh / 2) * h)
        x2 = min(float(w), (cx + bw / 2) * w)
        y2 = min(float(h), (cy + bh / 2) * h)
        box = {
            "cls_id": output_cls_id,
            "cls_name": mapped_name,
            "conf": 1.0,
            "xyxy": [x1, y1, x2, y2],
        }
        if original_name != mapped_name or output_cls_id != cls_id:
            box["original_cls_id"] = cls_id
            box["original_cls_name"] = original_name
        if unknown_label:
            box["unknown_label"] = True
        boxes.append(box)
    return boxes


__all__ = ["LABEL_MAP_PRESETS", "import_yolo_dataset_to_queue", "label_map_for_preset"]
