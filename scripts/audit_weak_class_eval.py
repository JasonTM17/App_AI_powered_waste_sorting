"""Audit weak-class YOLO failures and write contact sheets."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.weak_eval_audit import (  # noqa: E402
    PHASE16_FOCUS_CLASSES,
    class_id_mismatches,
    match_detections,
    source_anchor_counts,
    split_dir,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", choices=["train", "valid", "val", "test"], default="test")
    parser.add_argument("--queue", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--out", type=Path, default=Path("runs/eval/weak-class-audit.json"))
    parser.add_argument("--contact-dir", type=Path, default=Path("runs/eval/weak-class-contact-sheets"))
    parser.add_argument("--imgsz", type=int, default=576)
    parser.add_argument("--conf", type=float, default=0.05)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--max-det", type=int, default=100)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    names = _read_data_names(args.data)
    image_dir = split_dir(args.data.parent, args.split)
    images = sorted(image_dir.glob("*.jpg"))
    if args.limit > 0:
        images = images[: args.limit]
    source_index = _source_index(args.queue)
    audit = _run_audit(args.model, images, names, source_index, args)
    audit["class_id_mismatches"] = class_id_mismatches(names)
    audit["source_anchor_counts"] = source_anchor_counts(audit["items"], PHASE16_FOCUS_CLASSES)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_contact_sheets(audit["failures"], args.contact_dir)
    print(f"Weak-class audit written to {args.out}")
    print(f"Contact sheets: {args.contact_dir}")
    return 0


def _run_audit(
    model_path: Path,
    images: list[Path],
    names: dict[int, str],
    source_index: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    summary: dict[str, Counter[str]] = defaultdict(Counter)
    failures: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    focus = set(PHASE16_FOCUS_CLASSES)
    for image_path in images:
        gts = _read_gt(image_path, names)
        if not any(gt["class_name"] in focus for gt in gts):
            continue
        result = model.predict(
            source=str(image_path),
            imgsz=args.imgsz,
            conf=args.conf,
            iou=0.7,
            max_det=args.max_det,
            device=0,
            verbose=False,
        )[0]
        preds = _predictions(result, names)
        matched = match_detections(gts, preds, focus_classes=focus, iou_threshold=args.iou)
        meta = source_index.get(image_path.name, {})
        source = str(meta.get("source") or "exported")
        original_split = str(meta.get("split") or "")
        classes = sorted({gt["class_name"] for gt in gts if gt["class_name"] in focus})
        items.append(
            {
                "image": str(image_path),
                "source": source,
                "split": args.split,
                "original_meta_split": original_split,
                "classes": classes,
            }
        )
        for class_name, counts in matched["counts"].items():
            summary[class_name].update(counts)
            summary[class_name][f"source:{source}"] += 1
            summary[class_name][f"split:{args.split}"] += 1
            if original_split:
                summary[class_name][f"original_split:{original_split}"] += 1
        for row in matched["failures"]:
            row.update(
                {
                    "image": str(image_path),
                    "source": source,
                    "split": args.split,
                    "original_meta_split": original_split,
                    "all_gt": gts,
                    "all_pred": preds,
                }
            )
            failures.append(row)
    return {
        "model": str(model_path),
        "data": str(args.data),
        "split": args.split,
        "focus_classes": list(PHASE16_FOCUS_CLASSES),
        "summary": {name: dict(summary[name]) for name in sorted(summary)},
        "failures": failures,
        "items": items,
    }


def _read_data_names(path: Path) -> dict[int, str]:
    names: dict[int, str] = {}
    in_names = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("names:"):
            in_names = True
            continue
        if not in_names or ":" not in line:
            continue
        left, right = line.strip().split(":", 1)
        if left.isdigit():
            names[int(left)] = right.strip().strip("'\"")
    return names


def _read_gt(image_path: Path, names: dict[int, str]) -> list[dict[str, Any]]:
    label_path = Path(str(image_path).replace("\\images\\", "\\labels\\")).with_suffix(".txt")
    if not label_path.exists():
        label_path = image_path.parent.parent.parent / "labels" / image_path.parent.name / f"{image_path.stem}.txt"
    try:
        width, height = Image.open(image_path).size
    except OSError:
        return []
    rows = []
    for line in label_path.read_text(encoding="utf-8").splitlines() if label_path.exists() else []:
        parts = line.split()
        if len(parts) < 5:
            continue
        cls_id = int(float(parts[0]))
        cx, cy, bw, bh = (float(value) for value in parts[1:5])
        x1 = (cx - bw / 2) * width
        y1 = (cy - bh / 2) * height
        x2 = (cx + bw / 2) * width
        y2 = (cy + bh / 2) * height
        rows.append({"class_id": cls_id, "class_name": names.get(cls_id, str(cls_id)), "xyxy": (x1, y1, x2, y2)})
    return rows


def _predictions(result: Any, names: dict[int, str]) -> list[dict[str, Any]]:
    rows = []
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return rows
    for box in boxes:
        cls_id = int(box.cls[0])
        x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
        rows.append(
            {
                "class_id": cls_id,
                "class_name": names.get(cls_id, str(cls_id)),
                "conf": float(box.conf[0]),
                "xyxy": (x1, y1, x2, y2),
            }
        )
    return rows


def _source_index(queue_dir: Path) -> dict[str, dict[str, Any]]:
    index = {}
    for meta_path in queue_dir.glob("*.json") if queue_dir.exists() else []:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(meta, dict):
            index[f"{meta_path.stem}.jpg"] = meta
    return index


def _write_contact_sheets(failures: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in failures:
        if len(by_class[row["class_name"]]) < 24:
            by_class[row["class_name"]].append(row)
    for class_name, rows in by_class.items():
        _write_sheet(class_name, rows, out_dir / f"{_safe_name(class_name)}.jpg")


def _write_sheet(class_name: str, rows: list[dict[str, Any]], out_path: Path) -> None:
    cell_w, cell_h, label_h, cols = 220, 170, 70, 4
    sheet = Image.new("RGB", (cols * cell_w, max(1, (len(rows) + cols - 1) // cols) * (cell_h + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, row in enumerate(rows):
        image = Image.open(row["image"]).convert("RGB")
        _draw_boxes(image, row.get("all_gt", []), "red")
        _draw_boxes(image, row.get("all_pred", []), "blue")
        image.thumbnail((cell_w, cell_h))
        x, y = (idx % cols) * cell_w, (idx // cols) * (cell_h + label_h)
        sheet.paste(image, (x + (cell_w - image.width) // 2, y))
        label = f"{idx} {row['kind']} {class_name}\n{row.get('source','')}\nconf={row.get('pred_conf')}"
        draw.text((x + 4, y + cell_h + 2), label[:120], fill=(0, 0, 0))
    sheet.save(out_path, quality=92)


def _draw_boxes(image: Image.Image, boxes: list[dict[str, Any]], color: str) -> None:
    draw = ImageDraw.Draw(image)
    for box in boxes:
        xyxy = box.get("xyxy")
        if xyxy:
            draw.rectangle(tuple(float(v) for v in xyxy), outline=color, width=3)


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


if __name__ == "__main__":
    raise SystemExit(main())
