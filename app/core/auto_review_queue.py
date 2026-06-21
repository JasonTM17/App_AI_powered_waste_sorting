"""Safe, deduplicated capture of uncertain live-recognition frames."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from app.core.events import Detection
from app.utils.camera_frame_quality import evaluate_frame_quality
from app.utils.logging import logger


@dataclass
class AutoReviewQueue:
    """Capture one representative uncertain frame, never a frame-by-frame flood."""

    output_dir: Path
    cooldown_seconds: float = 12.0
    catalog_path: Path | None = None
    max_recent_hashes: int = 96
    _recent: dict[str, tuple[float, bytes]] = field(default_factory=dict)
    _session_id: str = field(default_factory=lambda: f"auto_review_{uuid.uuid4().hex[:12]}")
    _catalog: object | None = field(default=None, init=False, repr=False)

    def capture(
        self,
        frame_bgr: np.ndarray,
        detections: list[Detection],
        *,
        reason: str,
        ts: datetime,
        extra_meta: dict[str, object] | None = None,
    ) -> Path | None:
        if frame_bgr is None or frame_bgr.size == 0:
            return None
        fingerprint = _frame_fingerprint(frame_bgr)
        fingerprint_hex = fingerprint.hex()
        object_signature = _object_signature(frame_bgr, detections, reason)
        review_priority = _review_priority(reason, detections)
        suggested_label = _suggested_label(detections)
        now = time.monotonic()
        recent_key = f"{reason}:{object_signature}"
        previous = self._recent.get(recent_key)
        if previous is not None:
            previous_at, previous_hash = previous
            within_same_object_window = now - previous_at < self.cooldown_seconds
            looks_like_same_scene = _hamming_distance(fingerprint, previous_hash) <= 72
            if within_same_object_window or looks_like_same_scene:
                return None

        now_epoch = time.time()
        catalog = self._catalog_instance()
        if catalog is not None:
            try:
                if catalog.has_recent_review_capture(
                    object_signature=object_signature,
                    reason=reason,
                    frame_fingerprint=fingerprint_hex,
                    now_epoch=now_epoch,
                    cooldown_seconds=self.cooldown_seconds,
                    similar_scene_seconds=max(60.0, self.cooldown_seconds * 4.0),
                ):
                    self._recent[recent_key] = (now, fingerprint)
                    self._trim_recent()
                    return None
            except Exception as exc:
                logger.warning("auto review persistent dedupe failed: {}", exc)

        import cv2

        self.output_dir.mkdir(parents=True, exist_ok=True)
        uid = f"auto_review_{uuid.uuid4().hex[:12]}"
        image_path = self.output_dir / f"{uid}.jpg"
        if not cv2.imwrite(str(image_path), frame_bgr):
            logger.warning("auto review queue could not write {}", image_path)
            return None
        quality = evaluate_frame_quality(frame_bgr)
        metadata: dict[str, object] = {
            "ts": ts.isoformat(),
            "source": "auto_review_queue",
            "reviewed": False,
            "bbox_reviewed": False,
            "needs_annotation": True,
            "review_required": True,
            "training_excluded": True,
            "training_exclusion_reason": "awaiting_manual_annotation",
            "recognition_enabled": False,
            "queue_reason": reason,
            "object_signature": object_signature,
            "session_id": self._session_id,
            "suggested_label": suggested_label,
            "review_priority": review_priority,
            "is_screenshot_audit": False,
            "perceptual_hash": fingerprint_hex,
            "frame_fingerprint": fingerprint_hex,
            "quality": quality.to_dict(),
            "boxes": [
                {
                    "cls_id": detection.cls_id,
                    "cls_name": detection.cls_name,
                    "operator_label": detection.operator_label,
                    "conf": round(float(detection.conf), 4),
                    "xyxy": list(detection.xyxy),
                    "source": detection.source,
                }
                for detection in detections
            ],
        }
        if extra_meta:
            metadata.update(extra_meta)
        image_path.with_suffix(".json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._recent[recent_key] = (now, fingerprint)
        self._trim_recent()
        if catalog is not None:
            try:
                catalog.upsert_item(image_path, metadata)
                catalog.record_review_capture(
                    object_signature=object_signature,
                    reason=reason,
                    frame_fingerprint=fingerprint_hex,
                    session_id=self._session_id,
                    item_id=image_path.stem,
                    captured_at_epoch=now_epoch,
                )
            except Exception as exc:
                logger.warning("auto review queue catalog update failed: {}", exc)
        return image_path

    def _catalog_instance(self):
        if self._catalog is not None:
            return self._catalog
        try:
            from app.core.dataset_catalog import DatasetCatalog
            from app.utils.paths import dataset_db_path

            self._catalog = DatasetCatalog(self.catalog_path or dataset_db_path())
        except Exception as exc:
            logger.warning("auto review queue catalog unavailable: {}", exc)
            return None
        return self._catalog

    def _trim_recent(self) -> None:
        if len(self._recent) <= self.max_recent_hashes:
            return
        oldest = sorted(self._recent, key=lambda key: self._recent[key][0])
        for key in oldest[: len(self._recent) - self.max_recent_hashes]:
            self._recent.pop(key, None)


def _frame_fingerprint(frame_bgr: np.ndarray) -> bytes:
    import cv2

    gray = cv2.cvtColor(frame_bgr[:, :, :3], cv2.COLOR_BGR2GRAY)
    tiny = cv2.resize(gray, (16, 16), interpolation=cv2.INTER_AREA)
    median = int(np.median(tiny))
    return np.packbits((tiny >= median).astype(np.uint8)).tobytes()


def _hamming_distance(first: bytes, second: bytes) -> int:
    return sum((left ^ right).bit_count() for left, right in zip(first, second, strict=True))


def _object_signature(frame_bgr: np.ndarray, detections: list[Detection], reason: str) -> str:
    """Return a stable signature for one visible object/session, not one frame.

    The camera is slightly blurry and auto-exposure moves, so frame hashes alone
    change too often. This signature buckets the physical layout of detections
    so repeated low-confidence frames of the same charger, battery, pen, or comb
    are queued once per cooldown window.
    """
    height, width = frame_bgr.shape[:2]
    if width <= 0 or height <= 0:
        return f"{reason}:empty"
    parts: list[str] = [reason]
    for detection in sorted(detections, key=lambda item: (_label_key(item), item.xyxy)):
        x1, y1, x2, y2 = detection.xyxy
        box_width = max(1, int(x2 - x1))
        box_height = max(1, int(y2 - y1))
        cx_bucket = round(((x1 + x2) / 2.0) / width, 1)
        cy_bucket = round(((y1 + y2) / 2.0) / height, 1)
        area_bucket = round((box_width * box_height) / max(1, width * height), 1)
        aspect_bucket = round(min(8.0, box_width / box_height), 1)
        parts.append(
            f"{_label_key(detection)}@{cx_bucket},{cy_bucket},a{area_bucket},r{aspect_bucket}"
        )
    if len(parts) == 1:
        parts.append(_frame_fingerprint(frame_bgr).hex()[:8])
    raw = "|".join(parts)
    return hashlib.blake2b(raw.encode("utf-8"), digest_size=10).hexdigest()


def _label_key(detection: Detection) -> str:
    label = (detection.operator_label or detection.cls_name or "unknown").strip().casefold()
    if label.startswith("vật ") or label.startswith("vat "):
        return "foreground-fragment"
    if "unknown" in label:
        return "unknown"
    return label


def _suggested_label(detections: list[Detection]) -> str:
    for detection in sorted(detections, key=lambda item: item.conf, reverse=True):
        label = (detection.operator_label or "").strip()
        if label and "unknown" not in label.casefold() and not label.casefold().startswith(("vật ", "vat ")):
            return label
    for detection in sorted(detections, key=lambda item: item.conf, reverse=True):
        label = (detection.cls_name or "").strip()
        if label and label != "Unknown object":
            return label
    return ""


def _review_priority(reason: str, detections: list[Detection]) -> str:
    reason_key = reason.casefold()
    labels = " ".join(
        f"{detection.cls_name} {detection.operator_label}" for detection in detections
    ).casefold()
    if "battery" in labels or "pin" in labels or reason_key == "hazardous_battery":
        return "hazardous"
    if "unknown" in reason_key or "unknown" in labels:
        return "high"
    if "multiple" in reason_key or "foreground" in reason_key:
        return "high"
    if "low_confidence" in reason_key:
        return "medium"
    return "normal"


__all__ = ["AutoReviewQueue"]
