"""Run a detection-only safety evaluation over a hard-negative manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.inference import InferenceEngine  # noqa: E402
from app.core.waste_categories import canonical_class_name  # noqa: E402


def run_safety_eval(
    manifest_path: Path,
    model_path: Path,
    *,
    conf: float = 0.4,
    iou: float = 0.45,
    imgsz: int = 640,
    device: str = "auto",
    roi: tuple[int, int, int, int] | None = None,
) -> dict[str, Any]:
    rows = _load_manifest(manifest_path)
    engine = InferenceEngine(model_path, device=device, conf=conf, iou=iou, imgsz=imgsz)
    results: list[dict[str, Any]] = []
    passed = 0
    for row in rows:
        image_path = _manifest_image_path(manifest_path, row)
        detections = engine.predict(_read_bgr(image_path))
        ok, detail = _evaluate_expected_outcome(str(row.get("expected_outcome") or ""), detections, roi)
        passed += int(ok)
        results.append(
            {
                "image": str(row.get("image") or ""),
                "reason": str(row.get("reason") or ""),
                "expected_outcome": str(row.get("expected_outcome") or ""),
                "ok": ok,
                "detail": detail,
                "detections": [
                    {
                        "cls_id": det.cls_id,
                        "cls_name": det.cls_name,
                        "conf": det.conf,
                        "xyxy": list(det.xyxy),
                    }
                    for det in detections
                ],
            }
        )
    failures = [row for row in results if not row["ok"]]
    return {
        "manifest": str(manifest_path.resolve()),
        "model": str(model_path.resolve()),
        "total": len(results),
        "passed": passed,
        "failed": len(failures),
        "failures": failures[:50],
    }


def _evaluate_expected_outcome(
    expected: str,
    detections: list[Any],
    roi: tuple[int, int, int, int] | None,
) -> tuple[bool, str]:
    if expected == "no_detection":
        return len(detections) == 0, f"detections={len(detections)}"
    if expected == "no_dispatch":
        return len(detections) == 0, f"detections={len(detections)}"
    if expected == "multi_object_warning":
        classes = {
            canonical_class_name(str(det.cls_name)) or str(det.cls_name)
            for det in detections
        }
        return len(detections) >= 2, f"detections={len(detections)} distinct_classes={len(classes)}"
    if expected == "outside_roi_block":
        if not detections:
            return True, "no detections"
        if roi is None:
            return False, "roi is required to verify outside_roi_block"
        outside = [not _bbox_intersects_roi(det.xyxy, roi) for det in detections]
        return all(outside), f"outside_roi={sum(outside)}/{len(outside)}"
    return False, f"unknown expected_outcome={expected}"


def _bbox_intersects_roi(
    bbox: tuple[int, int, int, int],
    roi: tuple[int, int, int, int],
) -> bool:
    x1, y1, x2, y2 = bbox
    rx, ry, rw, rh = roi
    rx2 = rx + rw
    ry2 = ry + rh
    return max(x1, rx) < min(x2, rx2) and max(y1, ry) < min(y2, ry2)


def _load_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _manifest_image_path(manifest_path: Path, row: dict[str, Any]) -> Path:
    raw = Path(str(row.get("image") or ""))
    if raw.is_absolute():
        return raw
    return manifest_path.parent / raw


def _read_bgr(image_path: Path) -> np.ndarray:
    with Image.open(image_path) as image:
        rgb = np.asarray(image.convert("RGB"))
    return np.ascontiguousarray(rgb[:, :, ::-1])


def _parse_roi(value: str) -> tuple[int, int, int, int] | None:
    if not value.strip():
        return None
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--roi must be x,y,width,height")
    return tuple(parts)  # type: ignore[return-value]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("dataset_v2") / "safety_eval_pack" / "manifest.jsonl")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--conf", type=float, default=0.4)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--roi", type=_parse_roi, default=None, help="Optional x,y,width,height for outside-ROI checks.")
    parser.add_argument("--out", type=Path, default=Path("dataset_v2") / "safety_eval_report.json")
    args = parser.parse_args()

    report = run_safety_eval(
        args.manifest,
        args.model,
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        device=args.device,
        roi=args.roi,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Safety eval: {report['passed']}/{report['total']} passed, failed={report['failed']}")
    print(f"Report: {args.out.resolve()}")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
