"""Safe intake helpers for downloaded dataset ZIP packs."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from collections import Counter
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image

from app.core.dataset_catalog import DatasetCatalog
from app.core.waste_categories import (
    TRAINING_CLASS_ORDER_45,
    canonical_class_name,
    category_for_class,
    default_class_id_for_name,
)

DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE = "downloaded_anchor_bootstrap"
CAMERA_ANCHOR_ZIP_CLASSES = (
    "Pen",
    "Disposable tableware",
    "Ceramic",
    "Unknown plastic",
    "Electronics",
)
PHASE17_ZIP_NAMES = (
    "camera_anchor_recovery_dataset_v1.zip",
    "vietnam_waste50_dataset_kit.zip",
    "vietnam_3class_waste_dataset_builder.zip",
)

VIETNAM_WASTE50_TO_45 = {
    "foam_box": "Disposable tableware",
    "foam_food_box": "Disposable tableware",
    "styrofoam_box": "Disposable tableware",
    "disposable_spoon_fork": "Disposable tableware",
    "disposable_chopsticks": "Disposable tableware",
    "straw": "Disposable tableware",
    "plastic_straw": "Disposable tableware",
    "paper_cup": "Paper cups",
    "plastic_cup": "Plastic cup",
    "ceramic_broken": "Ceramic",
    "ceramic_bowl": "Ceramic",
    "small_electronics": "Electronics",
    "electrical_wire": "Electronics",
    "charging_cable": "Electronics",
    "circuit_board": "Electronics",
    "snack_wrapper": "Unknown plastic",
    "candy_wrapper": "Unknown plastic",
    "dirty_wrapper": "Unknown plastic",
    "medicine_blister": "Unknown plastic",
    "pen": "Pen",
    "ballpoint_pen": "Pen",
    "battery": "Battery",
    "toothbrush": "Toothbrush",
    "face_mask": "Textile",
    "banana_peel": "Organic",
    "orange_peel": "Organic",
    "vegetable_scraps": "Organic",
    "leftover_food": "Organic",
    "eggshell": "Organic",
    "coffee_grounds": "Organic",
    "tea_leaves": "Organic",
    "aluminum_can": "Aluminum can",
    "plastic_bottle": "Plastic bottle",
    "glass_bottle": "Glass bottle",
    "cardboard": "Cardboard",
    "paper": "Paper",
    "newspaper": "Paper",
    "plastic_bag": "Plastic bag",
    "tetra_pack": "Tetra pack",
    "milk_carton": "Tetra pack",
    "tin_can": "Tin",
    "food_can": "Tin",
    "plastic_cap": "Plastic caps",
    "aluminum_cap": "Aluminum caps",
    "foil": "Foil",
    "stretch_film": "Stretch film",
    "postal_packaging": "Postal packaging",
    "scrap_metal": "Scrap metal",
}

THREE_CLASS_TO_COMMAND = {
    "rac_huu_co": "O",
    "huu_co": "O",
    "organic": "O",
    "rac_vo_co": "R",
    "vo_co": "R",
    "inorganic": "R",
    "rac_tai_che": "I",
    "tai_che": "I",
    "recyclable": "I",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def audit_downloaded_zip(path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "zip_path": str(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else "",
        "warnings": [],
    }
    if not path.exists():
        report["warnings"].append("zip_missing")
        return report
    with zipfile.ZipFile(path) as zf:
        names = [item.filename for item in zf.infolist() if not item.is_dir()]
        suffixes = Counter(Path(name).suffix.lower() or "<none>" for name in names)
        report.update(
            {
                "file_count": len(names),
                "suffixes": dict(sorted(suffixes.items())),
                "image_count": sum(count for suffix, count in suffixes.items() if suffix in {".jpg", ".jpeg", ".png"}),
                "label_count": suffixes.get(".txt", 0),
                "files": names[:200],
            }
        )
        class_map = _read_json_member(zf, "class_map.json")
        report["class_map"] = class_map
        report["data_yaml"] = _read_text_member(zf, "yolo_weak/data.yaml", 20000)
        manifest = _read_csv_member(zf, "manifest.csv")
        sources = _read_csv_member(zf, "sources.csv")
        report["manifest_rows"] = len(manifest)
        report["source_rows"] = len(sources)
        report["source_license_complete"] = sum(1 for row in sources if _source_row_complete(row))
        weak_labels = Counter(str(row.get("label_type") or "") for row in manifest)
        report["manifest_label_types"] = dict(weak_labels)
        if any("full_image" in label for label in weak_labels):
            report["warnings"].append("weak_full_image_bbox_needs_manual_review")
        if class_map and set(class_map) <= set(CAMERA_ANCHOR_ZIP_CLASSES):
            report["warnings"].append("zip_uses_local_5_class_ids_not_project_45")
        taxonomy = _read_csv_member(zf, "vietnam_waste50_taxonomy.csv")
        if taxonomy:
            report["vietnam_waste50"] = _audit_vietnam50_rows(taxonomy)
        keyword_rows = _read_csv_member(zf, "keyword_mapping.csv")
        if keyword_rows:
            report["three_class_routes"] = _audit_three_class_rows(keyword_rows)
    return report


def map_vietnam_waste50_alias(alias: str) -> str:
    key = _key(alias)
    mapped = VIETNAM_WASTE50_TO_45.get(key) or VIETNAM_WASTE50_TO_45.get(_key(alias.replace("_", " ")))
    return canonical_class_name(mapped or alias.replace("_", " "))


def import_camera_anchor_zip_pending(
    zip_path: Path,
    queue_dir: Path,
    *,
    catalog_path: Path | None = None,
) -> dict[str, Any]:
    zip_hash = sha256_file(zip_path)
    queue_dir.mkdir(parents=True, exist_ok=True)
    catalog = DatasetCatalog(catalog_path) if catalog_path is not None else None
    imported: list[dict[str, str]] = []
    skipped: Counter[str] = Counter()
    try:
        with zipfile.ZipFile(zip_path) as zf:
            manifest = _read_csv_member(zf, "manifest.csv")
            sources = _sources_by_class(_read_csv_member(zf, "sources.csv"))
            existing = _existing_phase17_sources(queue_dir, zip_hash)
            for row in manifest:
                member = _safe_member(str(row.get("file") or row.get("image") or ""))
                if not member or member in existing:
                    skipped["duplicate_or_missing_member"] += 1
                    continue
                class_name = canonical_class_name(str(row.get("class") or ""))
                if class_name not in CAMERA_ANCHOR_ZIP_CLASSES:
                    skipped["class_not_allowed"] += 1
                    continue
                member = _resolve_image_member(zf, member, class_name)
                if not member:
                    skipped["duplicate_or_missing_member"] += 1
                    continue
                if member in existing:
                    skipped["duplicate_or_missing_member"] += 1
                    continue
                try:
                    raw = zf.read(member)
                    image = Image.open(BytesIO(raw)).convert("RGB")
                except (KeyError, OSError):
                    skipped["unreadable_image"] += 1
                    continue
                width, height = image.size
                target = queue_dir / f"downloaded_anchor_{zip_hash[:8].lower()}_{_stable_id(member)}.jpg"
                image.save(target, format="JPEG", quality=92)
                meta = _pending_meta(row, sources.get(class_name, {}), zip_path, zip_hash, member, class_name, width, height)
                target.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
                if catalog is not None:
                    catalog.upsert_item(target, meta)
                imported.append({"image": str(target), "class_name": class_name, "original_file": member})
    finally:
        if catalog is not None:
            catalog.close()
    return {
        "zip_path": str(zip_path),
        "zip_sha256": zip_hash,
        "source": DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE,
        "imported": len(imported),
        "skipped": dict(skipped),
        "items": imported[:200],
    }


def has_downloaded_bootstrap_source_metadata(meta: dict[str, Any]) -> bool:
    if str(meta.get("source") or "") != DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE:
        return True
    required = (
        meta.get("source_url"),
        meta.get("source_page_url"),
        meta.get("source_license") or meta.get("license"),
        meta.get("source_author"),
        meta.get("source_type"),
        meta.get("canonical_class"),
    )
    return all(str(value or "").strip() for value in required)


def _pending_meta(
    row: dict[str, str],
    source: dict[str, str],
    zip_path: Path,
    zip_hash: str,
    member: str,
    class_name: str,
    width: int,
    height: int,
) -> dict[str, Any]:
    class_id = default_class_id_for_name(class_name)
    source_license = source.get("license") or source.get("source_license") or ""
    return {
        "ts": datetime.now().isoformat(),
        "source": DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE,
        "reviewed": False,
        "needs_annotation": True,
        "training_excluded": True,
        "training_exclusion_reason": str(row.get("label_type") or "weak_full_image_bbox_needs_manual_review"),
        "recognition_enabled": False,
        "annotation_hint": "Review a tight bbox before any training or reference use.",
        "canonical_class": class_name,
        "source_url": source.get("image_url") or source.get("source_url") or "",
        "source_page_url": source.get("source_page_url") or source.get("source_page") or source.get("page_url") or "",
        "source_license": source_license,
        "license": source_license,
        "source_author": source.get("author") or source.get("source_author") or "",
        "source_type": source.get("source_type") or "downloaded_anchor_bootstrap",
        "phase17_downloaded_zip": True,
        "phase17_bootstrap_support": True,
        "real_anchor": False,
        "original_file": member,
        "source_zip": str(zip_path),
        "source_zip_sha256": zip_hash,
        "weak_label_type": str(row.get("label_type") or ""),
        "weak_full_image_bbox": True,
        "boxes": [{"cls_id": class_id, "cls_name": class_name, "conf": 1.0, "xyxy": [0, 0, width, height]}],
    }


def _audit_vietnam50_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    mapped: list[dict[str, Any]] = []
    for row in rows:
        alias = next((str(row.get(key) or "") for key in ("class", "name", "label", "slug") if row.get(key)), "")
        if not alias:
            continue
        canonical = map_vietnam_waste50_alias(alias)
        mapped.append({"alias": alias, "canonical_class": canonical, "command": category_for_class(canonical).code})
    return {"rows": len(rows), "mapped": mapped, "unmapped": [m["alias"] for m in mapped if m["canonical_class"] not in TRAINING_CLASS_ORDER_45]}


def _audit_three_class_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    routes: Counter[str] = Counter()
    for row in rows:
        value = next((str(v) for v in row.values() if _key(str(v)) in THREE_CLASS_TO_COMMAND), "")
        command = THREE_CLASS_TO_COMMAND.get(_key(value))
        if command:
            routes[command] += 1
    return {"rows": len(rows), "routes": dict(routes)}


def _sources_by_class(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {canonical_class_name(str(row.get("class") or row.get("canonical_class") or "")): row for row in rows}


def _existing_phase17_sources(queue_dir: Path, zip_hash: str) -> set[str]:
    existing = set()
    for meta_path in queue_dir.glob("*.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("source_zip_sha256") == zip_hash and meta.get("original_file"):
            existing.add(str(meta["original_file"]))
    return existing


def _read_text_member(zf: zipfile.ZipFile, member: str, limit: int = 100000) -> str:
    target = member
    if target not in zf.namelist():
        basename = PurePosixPath(member).name
        target = next((name for name in zf.namelist() if PurePosixPath(name).name == basename), member)
    try:
        return zf.read(target)[:limit].decode("utf-8", errors="replace")
    except KeyError:
        return ""


def _read_json_member(zf: zipfile.ZipFile, member: str) -> Any:
    text = _read_text_member(zf, member)
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _read_csv_member(zf: zipfile.ZipFile, member: str) -> list[dict[str, str]]:
    text = _read_text_member(zf, member)
    return list(csv.DictReader(StringIO(text))) if text else []


def _safe_member(value: str) -> str:
    member = value.replace("\\", "/").strip()
    parts = PurePosixPath(member).parts
    return "" if not member or any(part == ".." for part in parts) else member


def _source_row_complete(row: dict[str, str]) -> bool:
    source_page = row.get("source_page_url") or row.get("source_page")
    return all(
        str(value or "").strip()
        for value in (row.get("image_url"), source_page, row.get("license"), row.get("author"))
    )


def _resolve_image_member(zf: zipfile.ZipFile, member: str, class_name: str) -> str:
    names = {name for name in zf.namelist() if not name.endswith("/")}
    if member in names:
        return member
    basename = PurePosixPath(member).name
    class_folder = class_name.replace(" ", "_")
    candidates = [
        name
        for name in names
        if PurePosixPath(name).name == basename and f"/{class_folder}/" in f"/{name}"
    ]
    if candidates:
        return sorted(candidates, key=len)[0]
    candidates = [name for name in names if PurePosixPath(name).name == basename]
    return sorted(candidates, key=len)[0] if candidates else ""


def _stable_id(value: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9]+", "_", Path(value).stem).strip("_").lower()[:32]
    return f"{hashlib.sha1(value.encode()).hexdigest()[:10]}_{stem or 'image'}"


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


__all__ = [
    "CAMERA_ANCHOR_ZIP_CLASSES",
    "DOWNLOADED_ANCHOR_BOOTSTRAP_SOURCE",
    "PHASE17_ZIP_NAMES",
    "THREE_CLASS_TO_COMMAND",
    "VIETNAM_WASTE50_TO_45",
    "audit_downloaded_zip",
    "has_downloaded_bootstrap_source_metadata",
    "import_camera_anchor_zip_pending",
    "map_vietnam_waste50_alias",
    "sha256_file",
]
