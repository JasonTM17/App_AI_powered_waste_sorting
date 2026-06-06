"""Guided, quality-gated camera capture sessions."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from app.core.dataset_queue import import_manual_camera_frame


@dataclass
class CaptureSession:
    session_id: str
    cls_name: str
    cls_id: int
    target_count: int
    holdout_count: int
    started_at: float = field(default_factory=time.time)
    accepted_paths: list[str] = field(default_factory=list)
    holdout_paths: list[str] = field(default_factory=list)
    hashes: list[int] = field(default_factory=list)
    rejected_count: int = 0
    last_message: str = "Ready for first pose"
    active: bool = True

    def payload(self) -> dict[str, object]:
        return {
            "active": self.active,
            "session_id": self.session_id,
            "cls_name": self.cls_name,
            "cls_id": self.cls_id,
            "target_count": self.target_count,
            "holdout_count": self.holdout_count,
            "accepted_count": len(self.accepted_paths),
            "training_count": len(self.accepted_paths) - len(self.holdout_paths),
            "holdout_accepted": len(self.holdout_paths),
            "rejected_count": self.rejected_count,
            "last_message": self.last_message,
            "last_image_path": self.accepted_paths[-1] if self.accepted_paths else "",
        }


class CaptureSessionManager:
    def __init__(self, queue_dir: Path, catalog_path: Path) -> None:
        self.queue_dir = queue_dir
        self.catalog_path = catalog_path
        self._session: CaptureSession | None = None
        self._lock = Lock()

    @property
    def active(self) -> bool:
        with self._lock:
            return bool(self._session and self._session.active)

    def start(
        self,
        cls_name: str,
        cls_id: int,
        *,
        target_count: int = 24,
        holdout_count: int = 6,
    ) -> dict[str, object]:
        target = max(4, min(100, int(target_count)))
        holdout = max(1, min(target - 1, int(holdout_count)))
        with self._lock:
            self._session = CaptureSession(
                session_id=f"capture_{uuid.uuid4().hex[:12]}",
                cls_name=cls_name.strip(),
                cls_id=int(cls_id),
                target_count=target,
                holdout_count=holdout,
            )
            return self._session.payload()

    def status(self) -> dict[str, object]:
        with self._lock:
            if self._session is None:
                return _idle_payload()
            return self._session.payload()

    def stop(self) -> dict[str, object]:
        with self._lock:
            if self._session is None:
                return _idle_payload()
            self._session.active = False
            self._session.last_message = "Capture session stopped"
            return self._session.payload()

    def capture(
        self,
        frame_bgr: np.ndarray,
        bbox: tuple[int, int, int, int] | None,
        *,
        pose_index: int = 0,
    ) -> dict[str, object]:
        with self._lock:
            session = self._session
            if session is None or not session.active:
                raise RuntimeError("No active capture session")
            quality = evaluate_capture(frame_bgr, bbox, session.hashes)
            if not quality["accepted"]:
                session.rejected_count += 1
                session.last_message = str(quality["message"])
                return session.payload()

            accepted_index = len(session.accepted_paths) + 1
            is_holdout = _is_holdout_index(
                accepted_index,
                session.target_count,
                session.holdout_count,
            )
            metadata = {
                "capture_session_id": session.session_id,
                "capture_pose_index": max(0, int(pose_index)),
                "quality_score": quality["quality_score"],
                "blur_score": quality["blur_score"],
                "perceptual_hash": quality["hash_hex"],
                "split": "test" if is_holdout else "train",
                "split_lock": True,
                "holdout": is_holdout,
                "recognition_enabled": not is_holdout,
            }
            path = import_manual_camera_frame(
                frame_bgr,
                self.queue_dir,
                session.cls_name,
                session.cls_id,
                xyxy=bbox,
                catalog_path=self.catalog_path,
                extra_meta=metadata,
            )
            session.hashes.append(int(str(quality["hash_value"])))
            session.accepted_paths.append(str(path))
            if is_holdout:
                session.holdout_paths.append(str(path))
            session.last_message = (
                f"Accepted {accepted_index}/{session.target_count}"
                + (" as holdout" if is_holdout else "")
            )
            if accepted_index >= session.target_count:
                session.active = False
                session.last_message = "Capture target completed; review all bounding boxes"
            return session.payload()


def evaluate_capture(
    frame_bgr: np.ndarray,
    bbox: tuple[int, int, int, int] | None,
    previous_hashes: list[int],
) -> dict[str, object]:
    frame = np.asarray(frame_bgr)
    if frame.ndim != 3 or frame.shape[2] < 3:
        return _rejected("Invalid camera frame")
    height, width = frame.shape[:2]
    box = _clamp_box(bbox or (0, 0, width, height), width, height)
    x1, y1, x2, y2 = box
    area_ratio = ((x2 - x1) * (y2 - y1)) / float(max(1, width * height))
    if area_ratio < 0.003:
        return _rejected("Object box is too small; move the pen closer")
    if area_ratio > 0.9:
        return _rejected("Object box covers the whole frame; adjust the bounding box")
    px1, py1, px2, py2 = _padded_box(box, width, height)
    crop = frame[py1:py2, px1:px2, :3]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur_score < 35.0:
        return _rejected("Frame is too blurry; hold the pen still", blur_score)
    hash_value = _difference_hash(gray)
    if any((hash_value ^ old).bit_count() <= 4 for old in previous_hashes):
        return _rejected("Frame is too similar; rotate or move the pen", blur_score)
    quality_score = min(1.0, blur_score / 220.0) * min(1.0, area_ratio / 0.03)
    return {
        "accepted": True,
        "message": "Accepted",
        "blur_score": round(blur_score, 3),
        "quality_score": round(float(quality_score), 4),
        "hash_value": hash_value,
        "hash_hex": f"{hash_value:016x}",
    }


def _difference_hash(gray: np.ndarray) -> int:
    resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = resized[:, 1:] > resized[:, :-1]
    value = 0
    for bit in bits.flat:
        value = (value << 1) | int(bool(bit))
    return value


def _is_holdout_index(index: int, target: int, holdout: int) -> bool:
    return ((index * holdout) // target) > (((index - 1) * holdout) // target)


def _clamp_box(
    bbox: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(int(x1), width - 1))
    y1 = max(0, min(int(y1), height - 1))
    x2 = max(x1 + 1, min(int(x2), width))
    y2 = max(y1 + 1, min(int(y2), height))
    return x1, y1, x2, y2


def _padded_box(
    box: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    pad_x = max(4, int((x2 - x1) * 0.15))
    pad_y = max(4, int((y2 - y1) * 0.30))
    return (
        max(0, x1 - pad_x),
        max(0, y1 - pad_y),
        min(width, x2 + pad_x),
        min(height, y2 + pad_y),
    )


def _rejected(message: str, blur_score: float = 0.0) -> dict[str, object]:
    return {
        "accepted": False,
        "message": message,
        "blur_score": round(blur_score, 3),
        "quality_score": 0.0,
        "hash_value": 0,
        "hash_hex": "",
    }


def _idle_payload() -> dict[str, object]:
    return {
        "active": False,
        "session_id": "",
        "cls_name": "",
        "cls_id": 0,
        "target_count": 24,
        "holdout_count": 6,
        "accepted_count": 0,
        "training_count": 0,
        "holdout_accepted": 0,
        "rejected_count": 0,
        "last_message": "No active capture session",
        "last_image_path": "",
    }


__all__ = ["CaptureSessionManager", "evaluate_capture"]
