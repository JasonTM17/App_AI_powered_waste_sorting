"""Pure dataset queue helpers shared by desktop and local web agent."""

from __future__ import annotations

import json
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from app.core.dataset_catalog import DatasetCatalog
from app.core.downloaded_zip_intake import (
    DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE,
    has_downloaded_bootstrap_source_metadata,
)

TRUSTED_SOURCES = {
    "auto_low_conf",
    "manual_import",
    "manual_camera_capture",
    "manual_web_import",
    "roboflow",
    DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE,
}
REVIEW_REQUIRED_SOURCES = {
    "auto_low_conf",
    "manual_camera_capture",
    "manual_web_import",
    DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE,
}
MAX_MANUAL_URL_BYTES = 10 * 1024 * 1024
MANUAL_IMPORT_USER_AGENT = "TrashSorterPro/2.0 (jasonbmt06@gmail.com) manual-training-import"


def summarize_queue(queue_dir: Path) -> dict:
    images = sorted(queue_dir.glob("*.jpg")) if queue_dir.exists() else []
    classes: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    boxes = 0
    missing_meta = 0
    untrusted = 0
    for img in images:
        meta_file = img.with_suffix(".json")
        if not meta_file.exists():
            missing_meta += 1
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            missing_meta += 1
            continue
        source = meta.get("source") or "unknown"
        sources[source] += 1
        if not is_trusted_meta(meta):
            untrusted += 1
        for box in meta.get("boxes") or []:
            boxes += 1
            classes[box.get("cls_name") or "?"] += 1
    return {
        "images": len(images),
        "boxes": boxes,
        "classes": classes,
        "sources": sources,
        "auto": sources.get("auto_low_conf", 0),
        "manual": _sum_sources(
            sources,
            "manual_import",
            "manual_camera_capture",
            "manual_web_import",
        ),
        "roboflow": _sum_sources(sources, "roboflow"),
        "unknown": sources.get("unknown", 0),
        "untrusted": untrusted,
        "missing_meta": missing_meta,
    }


def import_manual_images(
    image_paths: list[str] | tuple[str, ...],
    queue_dir: Path,
    cls_name: str,
    cls_id: int,
    *,
    catalog_path: Path | None = None,
) -> int:
    """Import user-selected images as labeled training queue items."""
    from PIL import Image

    class_name, class_id = _canonical_box_label(cls_name, cls_id)
    queue_dir.mkdir(parents=True, exist_ok=True)
    catalog = DatasetCatalog(catalog_path) if catalog_path is not None else None
    added = 0
    try:
        for raw in image_paths:
            src = Path(raw)
            if not src.exists():
                continue
            try:
                with Image.open(src) as im:
                    rgb = im.convert("RGB")
                    w, h = rgb.size
                    uid = uuid.uuid4().hex[:12]
                    img_path = queue_dir / f"manual_{uid}.jpg"
                    rgb.save(img_path, format="JPEG", quality=92)
            except Exception:
                continue

            meta = {
                "ts": datetime.now().isoformat(),
                "source": "manual_import",
                "original_file": str(src),
                "boxes": [
                    {
                        "cls_id": class_id,
                        "cls_name": class_name,
                        "conf": 1.0,
                        "xyxy": [0, 0, w, h],
                    }
                ],
            }
            img_path.with_suffix(".json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            if catalog is not None:
                catalog.upsert_item(img_path, meta)
            added += 1
        return added
    finally:
        if catalog is not None:
            catalog.close()


def import_manual_camera_frame(
    frame_bgr,
    queue_dir: Path,
    cls_name: str,
    cls_id: int,
    *,
    xyxy: list[float] | tuple[float, float, float, float] | None = None,
    catalog_path: Path | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> Path:
    """Save the latest camera frame as a manual sample pending annotation."""
    import numpy as np
    from PIL import Image

    class_name, class_id = _canonical_box_label(cls_name, cls_id)
    arr = np.asarray(frame_bgr)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError("camera frame must be a BGR image")
    rgb = np.ascontiguousarray(arr[:, :, :3][:, :, ::-1])
    image = Image.fromarray(rgb)
    width, height = image.size
    queue_dir.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex[:12]
    img_path = queue_dir / f"manual_camera_{uid}.jpg"
    image.save(img_path, format="JPEG", quality=92)
    box_xyxy: list[float]
    if xyxy is None:
        box_xyxy = [0, 0, width, height]
    else:
        x1, y1, x2, y2 = (float(value) for value in list(xyxy)[:4])
        box_xyxy = [
            max(0.0, min(float(width), x1)),
            max(0.0, min(float(height), y1)),
            max(0.0, min(float(width), x2)),
            max(0.0, min(float(height), y2)),
        ]
        if box_xyxy[2] <= box_xyxy[0] or box_xyxy[3] <= box_xyxy[1]:
            box_xyxy = [0, 0, width, height]
    meta = {
        "ts": datetime.now().isoformat(),
        "source": "manual_camera_capture",
        "reviewed": False,
        "needs_annotation": True,
        "annotation_hint": "Review and adjust this box around the object before training.",
        "boxes": [
            {
                "cls_id": class_id,
                "cls_name": class_name,
                "conf": 1.0,
                "xyxy": box_xyxy,
            }
        ],
    }
    if extra_meta:
        meta.update(extra_meta)
    img_path.with_suffix(".json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if catalog_path is not None:
        catalog = DatasetCatalog(catalog_path)
        try:
            catalog.upsert_item(img_path, meta)
        finally:
            catalog.close()
    return img_path


def import_manual_image_urls(
    urls: list[str] | tuple[str, ...],
    queue_dir: Path,
    cls_name: str,
    cls_id: int,
    *,
    source_page_url: str = "",
    source_license: str = "",
    source_author: str = "",
    source_type: str = "licensed_url",
    generated: bool = False,
    extra_meta: dict[str, Any] | None = None,
    catalog_path: Path | None = None,
) -> int:
    """Import explicit image URLs as manual samples pending annotation."""
    from PIL import Image

    class_name, class_id = _canonical_box_label(cls_name, cls_id)
    queue_dir.mkdir(parents=True, exist_ok=True)
    catalog = DatasetCatalog(catalog_path) if catalog_path is not None else None
    added = 0
    try:
        for url in urls:
            clean_url = str(url or "").strip()
            if not clean_url:
                continue
            raw = _download_image_url(clean_url)
            try:
                with Image.open(BytesIO(raw)) as im:
                    rgb = im.convert("RGB")
                    width, height = rgb.size
                    uid = uuid.uuid4().hex[:12]
                    img_path = queue_dir / f"manual_web_{uid}.jpg"
                    rgb.save(img_path, format="JPEG", quality=92)
            except Exception as e:
                raise ValueError(f"URL is not a readable image: {clean_url}") from e
            meta = {
                "ts": datetime.now().isoformat(),
                "source": "manual_web_import",
                "reviewed": False,
                "needs_annotation": True,
                "recognition_enabled": not generated,
                "annotation_hint": "Review source rights and adjust this box before training.",
                "source_url": clean_url,
                "source_page_url": source_page_url,
                "source_license": source_license,
                "license": source_license,
                "source_author": source_author,
                "source_type": source_type,
                "canonical_class": class_name,
                "generated": bool(generated),
                "boxes": [
                    {
                        "cls_id": class_id,
                        "cls_name": class_name,
                        "conf": 1.0,
                        "xyxy": [0, 0, width, height],
                    }
                ],
            }
            if generated:
                meta["split"] = "train"
                meta["split_lock"] = True
            if extra_meta:
                meta.update(extra_meta)
            img_path.with_suffix(".json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            if catalog is not None:
                catalog.upsert_item(img_path, meta)
            added += 1
        return added
    finally:
        if catalog is not None:
            catalog.close()


def relabel_images(
    image_paths: list[Path],
    cls_name: str,
    cls_id: int,
    *,
    catalog_path: Path | None = None,
) -> int:
    class_name, class_id = _canonical_box_label(cls_name, cls_id)
    catalog = DatasetCatalog(catalog_path) if catalog_path is not None else None
    changed = 0
    try:
        for img in image_paths:
            meta_file = img.with_suffix(".json")
            if not img.exists() or not meta_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            boxes = meta.get("boxes") or []
            if not boxes:
                continue
            for box in boxes:
                box["cls_id"] = class_id
                box["cls_name"] = class_name
                box["conf"] = 1.0
            meta["reviewed"] = True
            meta["reviewed_at"] = datetime.now().isoformat()
            meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            if catalog is not None:
                catalog.upsert_item(img, meta)
            changed += 1
        return changed
    finally:
        if catalog is not None:
            catalog.close()


def delete_queue_items(image_paths: list[Path], *, catalog_path: Path | None = None) -> int:
    removed = 0
    removed_paths: list[Path] = []
    for img in image_paths:
        existed = img.exists()
        try:
            img.unlink(missing_ok=True)
            img.with_suffix(".json").unlink(missing_ok=True)
        except OSError:
            continue
        if existed:
            removed += 1
            removed_paths.append(img)
    if catalog_path is not None and removed_paths:
        catalog = DatasetCatalog(catalog_path)
        try:
            catalog.delete_by_image_paths(removed_paths)
        finally:
            catalog.close()
    return removed


def quarantine_queue_items(image_paths: list[Path], *, catalog_path: Path | None = None) -> int:
    if not image_paths:
        return 0
    target = image_paths[0].parent.parent / "quarantine" / datetime.now().strftime("%Y%m%d_%H%M%S")
    moved = 0
    moved_paths: list[Path] = []
    for img in image_paths:
        meta_file = img.with_suffix(".json")
        if not img.exists() or not meta_file.exists():
            continue
        target.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(img), str(target / img.name))
            shutil.move(str(meta_file), str(target / meta_file.name))
        except OSError:
            continue
        moved += 1
        moved_paths.append(img)
    if catalog_path is not None and moved_paths:
        catalog = DatasetCatalog(catalog_path)
        try:
            catalog.delete_by_image_paths(moved_paths)
        finally:
            catalog.close()
    return moved


def quarantine_untrusted_items(queue_dir: Path, *, catalog_path: Path | None = None) -> int:
    if not queue_dir.exists():
        return 0
    target = queue_dir.parent / "quarantine" / datetime.now().strftime("%Y%m%d_%H%M%S")
    moved = 0
    moved_paths: list[Path] = []
    for img in sorted(queue_dir.glob("*.jpg")):
        meta_file = img.with_suffix(".json")
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        if is_trusted_meta(meta):
            continue
        target.mkdir(parents=True, exist_ok=True)
        shutil.move(str(img), str(target / img.name))
        shutil.move(str(meta_file), str(target / meta_file.name))
        moved += 1
        moved_paths.append(img)
    if catalog_path is not None and moved_paths:
        catalog = DatasetCatalog(catalog_path)
        try:
            catalog.delete_by_image_paths(moved_paths)
        finally:
            catalog.close()
    return moved


def save_item_annotations(
    item_id: str,
    boxes: list[dict[str, Any]],
    *,
    catalog_path: Path,
) -> int:
    catalog = DatasetCatalog(catalog_path)
    try:
        item = catalog.get_item(item_id)
        if item is None:
            return 0
        img = Path(str(item["image_path"]))
        meta_file = img.with_suffix(".json")
        if not img.exists() or not meta_file.exists():
            return 0
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            return 0
        width, height = _image_size(img)
        clean_boxes = [_clean_box(box, width, height) for box in boxes]
        clean_boxes = [box for box in clean_boxes if box is not None]
        meta["boxes"] = clean_boxes
        meta["reviewed"] = True
        meta["needs_annotation"] = False
        meta["reviewed_at"] = datetime.now().isoformat()
        if str(meta.get("source") or "") == DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE:
            if has_downloaded_bootstrap_source_metadata(meta):
                meta["training_excluded"] = False
                meta["phase17_reviewed_train_support"] = True
                meta["split"] = "train"
                meta["split_lock"] = True
                meta["recognition_enabled"] = False
                meta["training_exclusion_reason_previous"] = meta.pop("training_exclusion_reason", "")
            else:
                meta["training_excluded"] = True
                meta["training_exclusion_reason"] = "missing_downloaded_source_metadata"
        meta.pop("unknown_labels", None)
        meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        catalog.upsert_item(img, meta)
        return 1
    finally:
        catalog.close()


def mark_items_trusted(
    image_paths: list[Path],
    *,
    trusted: bool,
    catalog_path: Path | None = None,
) -> int:
    catalog = DatasetCatalog(catalog_path) if catalog_path is not None else None
    changed = 0
    try:
        for img in image_paths:
            meta_file = img.with_suffix(".json")
            if not img.exists() or not meta_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            source = str(meta.get("source") or "unknown")
            if trusted:
                previous = str(meta.get("previous_source") or "")
                meta["source"] = previous if previous and previous != "untrusted" else (
                    source if source not in {"unknown", "untrusted"} else "manual_import"
                )
                meta.pop("unknown_labels", None)
            else:
                if source != "untrusted":
                    meta["previous_source"] = source
                meta["source"] = "untrusted"
                meta["unknown_labels"] = meta.get("unknown_labels") or ["marked_untrusted"]
            meta["reviewed"] = True
            meta["reviewed_at"] = datetime.now().isoformat()
            meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            if catalog is not None:
                catalog.upsert_item(img, meta)
            changed += 1
        return changed
    finally:
        if catalog is not None:
            catalog.close()


def is_trusted_meta(meta: dict) -> bool:
    source = str(meta.get("source") or "unknown")
    if source in {"unknown", "untrusted"}:
        return False
    return not meta.get("unknown_labels")


def is_trainable_meta(meta: dict) -> bool:
    if not is_trusted_meta(meta):
        return False
    if meta.get("training_excluded") is True:
        return False
    source = str(meta.get("source") or "unknown")
    return not (source in REVIEW_REQUIRED_SOURCES and not meta.get("reviewed"))


def _sum_sources(sources: Counter[str], prefix: str, *exact: str) -> int:
    total = sum(count for source, count in sources.items() if source == prefix or source.startswith(f"{prefix}_"))
    for source in exact:
        total += sources.get(source, 0)
    return total


def _download_image_url(url: str) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("image URL must start with http:// or https://")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": MANUAL_IMPORT_USER_AGENT},
    )
    data = b""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                content_type = response.headers.get("Content-Type", "")
                if content_type and not content_type.lower().startswith("image/"):
                    raise ValueError(f"URL content is not an image: {content_type}")
                data = response.read(MAX_MANUAL_URL_BYTES + 1)
                break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(_retry_after_seconds(e, attempt))
                continue
            raise ValueError(f"failed to download image URL: {e}") from e
        except urllib.error.URLError as e:
            raise ValueError(f"failed to download image URL: {e}") from e
    if len(data) > MAX_MANUAL_URL_BYTES:
        raise ValueError("image URL is larger than 10MB")
    if not data:
        raise ValueError("image URL returned empty content")
    return data


def _retry_after_seconds(error: urllib.error.HTTPError, attempt: int) -> float:
    raw = error.headers.get("Retry-After", "")
    try:
        return min(30.0, max(1.0, float(raw)))
    except (TypeError, ValueError):
        return float(2 ** (attempt + 1))


def _image_size(image_path: Path) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(image_path) as image:
            width, height = image.size
            return int(width), int(height)
    except Exception:
        return 1, 1


def _clean_box(box: dict[str, Any], width: int, height: int) -> dict[str, Any] | None:
    xyxy = box.get("xyxy") or []
    if len(xyxy) < 4:
        return None
    try:
        x1, y1, x2, y2 = (float(value) for value in xyxy[:4])
        cls_id = int(box.get("cls_id", 0))
    except (TypeError, ValueError):
        return None
    x1 = max(0.0, min(float(width), x1))
    y1 = max(0.0, min(float(height), y1))
    x2 = max(0.0, min(float(width), x2))
    y2 = max(0.0, min(float(height), y2))
    if x2 <= x1 or y2 <= y1:
        return None
    cls_name, cls_id = _canonical_box_label(box.get("cls_name") or cls_id, cls_id)
    conf = float(box.get("conf", 1.0) or 1.0)
    return {
        "cls_id": cls_id,
        "cls_name": cls_name,
        "conf": conf,
        "xyxy": [x1, y1, x2, y2],
    }


def _canonical_box_label(cls_name: object, cls_id: object) -> tuple[str, int]:
    from app.core.waste_categories import canonical_class_name, default_class_id_for_name

    raw_name = str(cls_name or "").strip()
    class_name = canonical_class_name(raw_name) or raw_name
    try:
        fallback_id = int(str(cls_id).strip())
    except (TypeError, ValueError):
        fallback_id = 0
    known_id = default_class_id_for_name(class_name)
    return class_name, fallback_id if known_id is None else known_id


__all__ = [
    "TRUSTED_SOURCES",
    "delete_queue_items",
    "import_manual_camera_frame",
    "import_manual_image_urls",
    "import_manual_images",
    "is_trainable_meta",
    "is_trusted_meta",
    "mark_items_trusted",
    "quarantine_queue_items",
    "quarantine_untrusted_items",
    "relabel_images",
    "save_item_annotations",
    "summarize_queue",
]
