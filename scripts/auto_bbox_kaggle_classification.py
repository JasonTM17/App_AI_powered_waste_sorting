"""Propose safe YOLO boxes for Kaggle classification-only images."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dataset_catalog import DatasetCatalog  # noqa: E402
from app.core.kaggle_intake import KAGGLE_AUTO_BBOX_CLASSIFICATION_SOURCE  # noqa: E402
from app.core.kaggle_real_image_pipeline import (  # noqa: E402
    read_manifest,
    route_for_canonical_class,
)
from app.core.phase18_anchor_tools import tight_bbox_candidate  # noqa: E402
from app.core.waste_categories import canonical_class_name, default_class_id_for_name  # noqa: E402
from app.utils.paths import dataset_db_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("dataset_v2") / "phase20_kaggle_classification_manifest.jsonl",
    )
    parser.add_argument("--model", type=Path, default=Path("models") / "best.pt")
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2") / "low_conf_queue")
    parser.add_argument("--catalog", type=Path, default=dataset_db_path())
    parser.add_argument("--out", type=Path, default=Path("dataset_v2") / "phase20_auto_bbox_report.json")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--max-per-class", type=int, default=0, help="0 means no per-class attempt cap.")
    parser.add_argument("--imgsz", type=int, default=576)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--device", default="0")
    parser.add_argument("--allow-bin-match", action="store_true")
    parser.add_argument("--foreground-proposals", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Import accepted detector boxes into the queue.")
    args = parser.parse_args()

    if not args.model.exists():
        raise SystemExit(f"model not found: {args.model}")
    if not args.manifest.exists():
        raise SystemExit(f"manifest not found: {args.manifest}")

    from ultralytics import YOLO

    model = YOLO(str(args.model))
    names = {int(k): str(v) for k, v in dict(model.names).items()}
    accepted: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    attempted_by_class: Counter[str] = Counter()
    attempted = 0
    existing_originals = _existing_original_files(args.queue) if args.apply else set()
    catalog = DatasetCatalog(args.catalog) if args.apply else None
    try:
        for row in read_manifest(args.manifest):
            if args.limit > 0 and attempted >= args.limit:
                break
            image_path = Path(str(row.get("source_path") or ""))
            expected_class = canonical_class_name(str(row.get("canonical_class") or ""))
            if args.max_per_class > 0 and attempted_by_class[expected_class] >= args.max_per_class:
                skipped["class_attempt_cap"] += 1
                continue
            if args.apply and str(image_path.resolve()) in existing_originals:
                skipped["already_imported"] += 1
                continue
            if not image_path.exists():
                skipped["missing_image"] += 1
                continue
            attempted += 1
            attempted_by_class[expected_class] += 1
            prediction = _predict_best(
                model,
                names,
                image_path,
                expected_class,
                str(row.get("bin_code") or ""),
                imgsz=args.imgsz,
                conf=args.conf,
                device=args.device,
                allow_bin_match=args.allow_bin_match,
            )
            if prediction is None:
                skipped["no_matching_prediction"] += 1
                if args.foreground_proposals:
                    bbox = tight_bbox_candidate(image_path)
                    if bbox is not None:
                        proposals.append({"source_path": str(image_path), "canonical_class": expected_class, "xyxy": bbox})
                continue
            item = {**row, **prediction, "accepted_at": datetime.now().isoformat()}
            accepted.append(item)
            if args.apply:
                _import_auto_bbox(args.queue, image_path, row, prediction, catalog)
                existing_originals.add(str(image_path.resolve()))
    finally:
        if catalog is not None:
            catalog.close()

    report = {
        "created_at": datetime.now().isoformat(),
        "manifest": str(args.manifest),
        "model": str(args.model),
        "apply": args.apply,
        "limit": args.limit,
        "max_per_class": args.max_per_class,
        "attempted": attempted,
        "attempted_by_class": dict(sorted(attempted_by_class.items())),
        "accepted": len(accepted),
        "skipped": dict(sorted(skipped.items())),
        "foreground_proposals": len(proposals),
        "accepted_items": accepted[:200],
        "proposal_items": proposals[:200],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"accepted_items", "proposal_items"}}, indent=2))
    print(f"Auto-bbox report: {args.out}")
    return 0


def _predict_best(
    model: Any,
    names: dict[int, str],
    image_path: Path,
    expected_class: str,
    expected_bin: str,
    *,
    imgsz: int,
    conf: float,
    device: str,
    allow_bin_match: bool,
) -> dict[str, Any] | None:
    results = model.predict(str(image_path), imgsz=imgsz, conf=conf, device=device, verbose=False)
    best: dict[str, Any] | None = None
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            cls_id = int(box.cls[0].item())
            pred_class = canonical_class_name(names.get(cls_id, str(cls_id)))
            pred_conf = float(box.conf[0].item())
            agreement = _agreement(pred_class, expected_class, expected_bin, allow_bin_match)
            if agreement is None:
                continue
            xyxy = [float(value) for value in box.xyxy[0].tolist()]
            candidate = {
                "xyxy": xyxy,
                "predicted_class": pred_class,
                "predicted_conf": pred_conf,
                "agreement": agreement,
            }
            if best is None or (agreement == "class" and best["agreement"] != "class") or pred_conf > best["predicted_conf"]:
                best = candidate
    return best


def _agreement(
    pred_class: str,
    expected_class: str,
    expected_bin: str,
    allow_bin_match: bool,
) -> str | None:
    if pred_class == expected_class:
        return "class"
    if allow_bin_match and route_for_canonical_class(pred_class).code == expected_bin:
        return "bin"
    return None


def _import_auto_bbox(
    queue: Path,
    image_path: Path,
    row: dict[str, Any],
    prediction: dict[str, Any],
    catalog: DatasetCatalog | None,
) -> None:
    queue.mkdir(parents=True, exist_ok=True)
    canonical = canonical_class_name(str(row.get("canonical_class") or ""))
    cls_id = default_class_id_for_name(canonical)
    if cls_id is None:
        return
    uid = uuid.uuid4().hex[:12]
    out_img = queue / f"{KAGGLE_AUTO_BBOX_CLASSIFICATION_SOURCE}_{uid}.jpg"
    try:
        with Image.open(image_path) as image:
            image.convert("RGB").save(out_img, format="JPEG", quality=92)
    except OSError:
        shutil.copy2(image_path, out_img)
    meta = {
        "ts": datetime.now().isoformat(),
        "source": KAGGLE_AUTO_BBOX_CLASSIFICATION_SOURCE,
        "source_dataset": row.get("source_dataset"),
        "source_type": "kaggle_classification_auto_bbox",
        "source_path": str(image_path),
        "original_file": str(image_path),
        "original_split": row.get("original_split"),
        "source_class": row.get("source_class"),
        "canonical_class": canonical,
        "bin_code": row.get("bin_code"),
        "reviewed": True,
        "needs_annotation": False,
        "recognition_enabled": False,
        "split": "train",
        "split_lock": True,
        "phase20_auto_bbox_train_support": True,
        "auto_bbox_agreement": prediction.get("agreement"),
        "auto_bbox_predicted_class": prediction.get("predicted_class"),
        "auto_bbox_predicted_conf": prediction.get("predicted_conf"),
        "boxes": [
            {
                "cls_id": cls_id,
                "cls_name": canonical,
                "conf": 1.0,
                "xyxy": prediction.get("xyxy"),
            }
        ],
    }
    out_img.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    if catalog is not None:
        catalog.upsert_item(out_img, meta)


def _existing_original_files(queue: Path) -> set[str]:
    values: set[str] = set()
    if not queue.exists():
        return values
    for meta_path in queue.glob("*.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(meta.get("source") or "") != KAGGLE_AUTO_BBOX_CLASSIFICATION_SOURCE:
            continue
        original = str(meta.get("original_file") or meta.get("source_path") or "").strip()
        if not original:
            continue
        values.add(original)
        try:
            values.add(str(Path(original).resolve()))
        except OSError:
            continue
    return values


if __name__ == "__main__":
    raise SystemExit(main())
