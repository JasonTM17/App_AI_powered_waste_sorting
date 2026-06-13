"""Conservative migrations for legacy dataset metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.dataset_catalog import DatasetCatalog
from app.core.dataset_trust import canonical_classes_from_meta


@dataclass(frozen=True)
class LegacyCameraReviewMigration:
    eligible: tuple[Path, ...]
    applied: tuple[Path, ...]


def backfill_legacy_camera_bbox_reviews(
    queue_dir: Path,
    *,
    apply: bool = False,
    catalog_path: Path | None = None,
) -> LegacyCameraReviewMigration:
    """Restore the bbox approval flag written by the legacy camera review UI."""
    eligible: list[Path] = []
    applied: list[Path] = []
    catalog = DatasetCatalog(catalog_path) if apply and catalog_path is not None else None
    try:
        for meta_path in sorted(queue_dir.glob("manual_camera_*.json")):
            meta = _read_meta(meta_path)
            if not _is_legacy_approved_camera_review(meta):
                continue
            eligible.append(meta_path)
            if not apply:
                continue
            meta["bbox_reviewed"] = True
            meta["needs_annotation"] = False
            meta["training_excluded"] = False
            meta.setdefault("recognition_enabled", True)
            meta["metadata_migration"] = "legacy_camera_review_bbox_v1"
            meta["metadata_migrated_at"] = datetime.now(UTC).isoformat()
            _write_meta_atomic(meta_path, meta)
            if catalog is not None:
                catalog.upsert_item(meta_path.with_suffix(".jpg"), meta)
            applied.append(meta_path)
    finally:
        if catalog is not None:
            catalog.close()
    return LegacyCameraReviewMigration(tuple(eligible), tuple(applied))


def _is_legacy_approved_camera_review(meta: dict) -> bool:
    if str(meta.get("source") or "") != "manual_camera_capture":
        return False
    if meta.get("reviewed") is not True or "bbox_reviewed" in meta:
        return False
    if not str(meta.get("reviewed_at") or "").strip():
        return False
    if meta.get("needs_annotation") is True or meta.get("training_excluded") is True:
        return False
    if meta.get("quarantined") is True:
        return False
    class_names, reasons = canonical_classes_from_meta(meta)
    return bool(class_names) and not reasons


def _read_meta(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_meta_atomic(path: Path, meta: dict) -> None:
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)
