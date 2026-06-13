"""Pipeline orchestrator: frame -> infer -> track -> labeled capture -> history -> uart."""

from __future__ import annotations

import io
import json
import time
import uuid
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.core.config import (
    AppConfig,
    ClassMapping,
    computer_speaker_enabled,
    normalize_multi_class_warning_text,
)
from app.core.dispatch_guard import DispatchGuard
from app.core.events import Detection, TrackedDetection
from app.core.hardware_profile import route_for_command
from app.core.history import HistoryService
from app.core.manual_reference_recognition import ManualReferenceRecognizer
from app.core.multi_object_dispatch import (
    evaluate_foreground_multi_object_dispatch,
    evaluate_single_class_dispatch,
)
from app.core.speaker import NoopSpeaker, Speaker
from app.core.three_bin_classifier import (
    THREE_BIN_SOURCE,
    ThreeBinClassifier,
    parse_three_bin_class_name,
)
from app.core.tracker import Tracker
from app.core.uart_protocol import encode_sort
from app.core.unknown_object_fallback import UnknownObjectFallback
from app.core.voice_pack import sort_voice_path
from app.core.waste_categories import (
    category_for_class,
    category_for_command,
    category_for_known_class,
    normalize_mapping_to_three_bins,
)
from app.utils.logging import logger
from app.utils.paths import detection_captures_dir


def _make_thumbnail(frame_bgr: np.ndarray, max_size=(100, 75)) -> bytes:
    rgb = frame_bgr[:, :, ::-1]
    img = Image.fromarray(rgb)
    img.thumbnail(max_size)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


class LabeledCapture(TypedDict):
    image_path: str | None
    annotated_path: str | None
    meta_path: str | None
    route_label: str | None
    bin_index: int | None


def _normalize_dispatch_mapping(mapping: ClassMapping) -> ClassMapping:
    return normalize_mapping_to_three_bins(mapping)


def _load_label_font(size: int = 18) -> Any:
    for candidate in (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _clamp_box(
    xyxy: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = xyxy
    x1 = max(0, min(int(x1), width - 1))
    y1 = max(0, min(int(y1), height - 1))
    x2 = max(x1 + 1, min(int(x2), width))
    y2 = max(y1 + 1, min(int(y2), height))
    return x1, y1, x2, y2


def _box_area_ratio(
    xyxy: tuple[int, int, int, int],
    width: int,
    height: int,
) -> float:
    if width <= 0 or height <= 0:
        return 0.0
    x1, y1, x2, y2 = _clamp_box(xyxy, width, height)
    return float((x2 - x1) * (y2 - y1)) / float(width * height)


class _NoopUart:
    def send(self, track_id, command, conf) -> None:
        logger.debug(
            "uart disabled; skipped dispatch track={} cmd={} conf={:.2f}",
            track_id,
            command,
            conf,
        )

    def send_silent(self, track_id, command, conf) -> None:
        self.send(track_id, command, conf)


class Pipeline:
    def __init__(
        self,
        cfg: AppConfig,
        engine,
        uart,
        history_db: Path,
        speaker: Speaker | None = None,
    ):
        self.cfg = cfg
        self.engine = engine
        self.uart = uart if uart is not None else _NoopUart()
        self.speaker = speaker if speaker is not None else NoopSpeaker()
        self.tracker = Tracker(iou_threshold=0.3, max_age=30)
        self.history = HistoryService(history_db)
        self._mapping = {m.class_name: m for m in cfg.mappings if m.enabled}
        self._track_to_row: dict[int, int] = {}
        self._track_to_speech: dict[int, tuple[str, int, str, float]] = {}
        self._unknown_fallback = UnknownObjectFallback()
        self._hardware_dispatch_enabled = True
        self.dispatch_status = "waiting empty tray"
        self._dispatch_guard = DispatchGuard()
        self._last_multi_class_warning_at = 0.0
        self._manual_reference_recognizer = self._build_manual_reference_recognizer()
        self._three_bin_classifier = self._build_three_bin_classifier()
        self._configure_dispatch_guard()
        self._foreground_gate_enabled = False
        self._foreground_background: np.ndarray | None = None
        self._foreground_background_frames = 0
        self._foreground_warmup_frames = 6
        self.on_capture_saved = None  # type: ignore[assignment]

    def update_config(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.update_mappings(cfg.mappings)
        self._configure_dispatch_guard()
        if self._manual_reference_recognizer is None:
            self._manual_reference_recognizer = self._build_manual_reference_recognizer()
        if self._manual_reference_recognizer is not None:
            ref_cfg = cfg.manual_reference_recognition
            self._manual_reference_recognizer.configure(
                enabled=ref_cfg.enabled,
                min_similarity=ref_cfg.min_similarity,
                min_consensus_similarity=ref_cfg.min_consensus_similarity,
                min_margin=ref_cfg.min_margin,
                top_k=ref_cfg.top_k,
                min_votes=ref_cfg.min_votes,
                max_references_per_class=ref_cfg.max_references_per_class,
                refresh_seconds=ref_cfg.cache_refresh_seconds,
                query_cache_seconds=ref_cfg.query_cache_seconds,
            )
        self._three_bin_classifier = self._build_three_bin_classifier()
        self._dispatch_guard.reset()
        self.dispatch_status = self._dispatch_guard.last_reason

    def update_mappings(self, mappings):
        self._mapping = {m.class_name: m for m in mappings if m.enabled}

    def set_uart(self, uart) -> None:
        self.uart = uart if uart is not None else _NoopUart()

    def set_hardware_dispatch_enabled(self, enabled: bool) -> None:
        self._hardware_dispatch_enabled = bool(enabled)

    @property
    def auto_sort_state(self) -> str:
        return self._dispatch_guard.state

    def set_dispatch_cooldown(self, seconds: float) -> None:
        self.cfg.dispatch_guard.min_sort_interval_seconds = max(0.0, float(seconds))
        self._configure_dispatch_guard()

    def set_min_dispatch_stable_frames(self, frames: int) -> None:
        self.cfg.dispatch_guard.min_stable_frames = max(1, int(frames))
        self._configure_dispatch_guard()

    def refresh_manual_references(self) -> None:
        if self._manual_reference_recognizer is not None:
            self._manual_reference_recognizer.refresh(force=True)

    def three_bin_classifier_status(self) -> dict[str, object]:
        if self._three_bin_classifier is None:
            return {"enabled": False, "ready": False, "message": "disabled"}
        return self._three_bin_classifier.status()

    def set_dispatch_foreground_gate(self, enabled: bool, warmup_frames: int = 6) -> None:
        self._foreground_gate_enabled = bool(enabled)
        self._foreground_warmup_frames = max(1, int(warmup_frames))
        self._reset_foreground_gate()

    def reset_dispatch_state(self) -> None:
        self.tracker.reset()
        self._unknown_fallback.reset()
        self._dispatch_guard.reset()
        self._track_to_row.clear()
        self._track_to_speech.clear()
        self._last_multi_class_warning_at = 0.0
        self.dispatch_status = self._dispatch_guard.last_reason
        self._reset_foreground_gate()

    def _configure_dispatch_guard(self) -> None:
        guard = self.cfg.dispatch_guard
        self._dispatch_guard.configure(
            min_sort_interval_seconds=guard.min_sort_interval_seconds,
            busy_settle_seconds=guard.busy_settle_seconds,
            min_stable_frames=guard.min_stable_frames,
            empty_rearm_seconds=guard.empty_rearm_seconds,
            empty_rearm_frames=guard.empty_rearm_frames,
        )

    def _build_manual_reference_recognizer(self) -> ManualReferenceRecognizer | None:
        ref_cfg = self.cfg.manual_reference_recognition
        if not ref_cfg.enabled:
            return None
        queue_dir = Path(self.cfg.capture.output_dir) / "low_conf_queue"
        return ManualReferenceRecognizer(
            queue_dir,
            enabled=ref_cfg.enabled,
            min_similarity=ref_cfg.min_similarity,
            min_consensus_similarity=ref_cfg.min_consensus_similarity,
            min_margin=ref_cfg.min_margin,
            top_k=ref_cfg.top_k,
            min_votes=ref_cfg.min_votes,
            max_references_per_class=ref_cfg.max_references_per_class,
            refresh_seconds=ref_cfg.cache_refresh_seconds,
            query_cache_seconds=ref_cfg.query_cache_seconds,
        )

    def _build_three_bin_classifier(self) -> ThreeBinClassifier | None:
        classifier_cfg = self.cfg.three_bin_classifier
        if not classifier_cfg.enabled:
            return None
        return ThreeBinClassifier(
            classifier_cfg.model_path,
            enabled=classifier_cfg.enabled,
            min_confidence=classifier_cfg.min_confidence,
            min_margin=classifier_cfg.min_margin,
            min_crop_area_ratio=classifier_cfg.min_crop_area_ratio,
            input_size=classifier_cfg.input_size,
        )

    def _reset_foreground_gate(self) -> None:
        self._foreground_background = None
        self._foreground_background_frames = 0

    def _has_uart(self) -> bool:
        if isinstance(self.uart, _NoopUart):
            return False
        connected = getattr(self.uart, "is_connected", None)
        if connected is not None and not bool(connected):
            return False
        is_running = getattr(self.uart, "isRunning", None)
        return not (callable(is_running) and not bool(is_running()))

    def _save_low_conf_frame(self, frame_bgr, detections, ts):
        if self.cfg.capture.mode != "auto_low_conf":
            return
        if not detections:
            return
        if all(d.conf >= self.cfg.capture.low_conf_threshold for d in detections):
            return

        import cv2

        out_dir = Path(self.cfg.capture.output_dir) / "low_conf_queue"
        out_dir.mkdir(parents=True, exist_ok=True)
        uid = uuid.uuid4().hex[:12]
        img_path = out_dir / f"{uid}.jpg"
        cv2.imwrite(str(img_path), frame_bgr)
        meta = {
            "ts": ts.isoformat(),
            "source": "auto_low_conf",
            "boxes": [
                {"cls_id": d.cls_id, "cls_name": d.cls_name, "conf": d.conf, "xyxy": list(d.xyxy)}
                for d in detections
            ],
        }
        (out_dir / f"{uid}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        try:
            from app.core.dataset_catalog import DatasetCatalog
            from app.utils.paths import dataset_db_path

            catalog = DatasetCatalog(dataset_db_path())
            try:
                catalog.upsert_item(img_path, meta)
            finally:
                catalog.close()
        except Exception as e:
            logger.warning("dataset catalog update failed: {}", e)
        cb = self.on_capture_saved
        if callable(cb):
            try:
                cb(str(img_path))
            except Exception as e:
                logger.warning("on_capture_saved callback failed: {}", e)

    def _save_route_consensus_review(
        self,
        frame_bgr: np.ndarray,
        detection: Detection,
        ts: datetime,
    ) -> str:
        import cv2

        out_dir = Path(self.cfg.capture.output_dir) / "low_conf_queue"
        out_dir.mkdir(parents=True, exist_ok=True)
        uid = f"route_consensus_{uuid.uuid4().hex[:12]}"
        img_path = out_dir / f"{uid}.jpg"
        if not cv2.imwrite(str(img_path), frame_bgr):
            raise OSError(f"could not write review frame: {img_path}")
        primary_route = self._mapping_for_detection(detection).command
        meta = {
            "ts": ts.isoformat(),
            "source": "route_consensus_review",
            "reviewed": False,
            "bbox_reviewed": False,
            "needs_annotation": True,
            "review_required": True,
            "training_excluded": True,
            "training_exclusion_reason": "route_consensus_blocked",
            "recognition_enabled": False,
            "route_consensus": {
                "primary_route": primary_route,
                "secondary_route": detection.secondary_route,
                "secondary_confidence": detection.secondary_confidence,
                "secondary_margin": detection.secondary_margin,
                "status": detection.route_consensus,
                "reason": detection.route_consensus_reason,
            },
            "boxes": [
                {
                    "cls_id": detection.cls_id,
                    "cls_name": detection.cls_name,
                    "conf": detection.conf,
                    "xyxy": list(detection.xyxy),
                }
            ],
        }
        img_path.with_suffix(".json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        try:
            from app.core.dataset_catalog import DatasetCatalog
            from app.utils.paths import dataset_db_path

            catalog = DatasetCatalog(dataset_db_path())
            try:
                catalog.upsert_item(img_path, meta)
            finally:
                catalog.close()
        except Exception as e:
            logger.warning("route consensus review catalog update failed: {}", e)
        cb = self.on_capture_saved
        if callable(cb):
            try:
                cb(str(img_path))
            except Exception as e:
                logger.warning("on_capture_saved callback failed: {}", e)
        return str(img_path)

    def _in_roi(self, xyxy):
        roi = self.cfg.roi
        if not roi.enabled or roi.width == 0 or roi.height == 0:
            return True
        x1, y1, x2, y2 = xyxy
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return roi.x <= cx <= roi.x + roi.width and roi.y <= cy <= roi.y + roi.height

    def _roi_ready_for_dispatch(self, frame_bgr: np.ndarray) -> bool:
        if not self.cfg.dispatch_guard.require_roi_for_dispatch:
            return True
        roi = self.cfg.roi
        if not roi.enabled or roi.width <= 0 or roi.height <= 0:
            return False
        height, width = frame_bgr.shape[:2]
        if roi.x < 0 or roi.y < 0:
            return False
        return roi.x < width and roi.y < height

    def _ack_timeout_seconds(self) -> float:
        return max(0.0, self.cfg.uart.ack_timeout_ms / 1000.0)

    def _foreground_changed_for_dispatch(self, frame_bgr: np.ndarray, xyxy) -> bool:
        if not self._foreground_gate_enabled:
            return True
        try:
            import cv2
        except Exception as e:
            logger.warning("foreground gate disabled because cv2 unavailable: {}", e)
            return True
        if frame_bgr.size == 0:
            return False
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (7, 7), 0)
        if self._foreground_background is None:
            self._foreground_background = gray.astype("float32")
            self._foreground_background_frames = 1
            return False
        if self._foreground_background_frames < self._foreground_warmup_frames:
            cv2.accumulateWeighted(gray, self._foreground_background, 0.35)
            self._foreground_background_frames += 1
            return False

        x1, y1, x2, y2 = _clamp_box(xyxy, gray.shape[1], gray.shape[0])
        background_u8 = cv2.convertScaleAbs(self._foreground_background)
        diff = cv2.absdiff(background_u8, gray)
        _, mask = cv2.threshold(diff, 32, 255, cv2.THRESH_BINARY)
        kernel = np.ones((3, 3), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        crop = mask[y1:y2, x1:x2]
        area = int(crop.size)
        if area <= 0:
            return False
        changed = int(np.count_nonzero(crop))
        changed_ratio = changed / float(area)
        return changed >= 48 and changed_ratio >= 0.02

    def _save_labeled_capture(self, frame_bgr, tracked: TrackedDetection, mapping) -> LabeledCapture:
        det = tracked.detection
        category = category_for_command(mapping.command)
        category_name = category.name if category is not None else f"Thùng {mapping.bin_index}"
        now = datetime.now()
        uid = f"{now:%Y%m%d-%H%M%S-%f}-t{tracked.track_id}-{uuid.uuid4().hex[:6]}"
        out_dir = detection_captures_dir() / f"{now:%Y-%m-%d}"
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_path = out_dir / f"{uid}.jpg"
        annotated_path = out_dir / f"{uid}-labeled.jpg"
        meta_path = out_dir / f"{uid}.json"

        rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])
        image = Image.fromarray(rgb)
        image.save(raw_path, format="JPEG", quality=92)

        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        width, height = annotated.size
        x1, y1, x2, y2 = _clamp_box(det.xyxy, width, height)
        font = _load_label_font()
        label = (
            f"{det.cls_name} {det.conf:.0%} | {category_name} | "
            f"Thùng {int(mapping.bin_index)}"
        )
        stroke = (16, 185, 129)
        fill = (4, 54, 38)
        draw.rectangle((x1, y1, x2, y2), outline=stroke, width=4)
        text_box = draw.textbbox((0, 0), label, font=font)
        text_w = text_box[2] - text_box[0]
        text_h = text_box[3] - text_box[1]
        label_x = x1
        label_y = max(0, y1 - text_h - 12)
        draw.rounded_rectangle(
            (label_x, label_y, min(width - 1, label_x + text_w + 14), label_y + text_h + 10),
            radius=4,
            fill=fill,
        )
        draw.text((label_x + 7, label_y + 5), label, font=font, fill=(255, 255, 255))
        annotated.save(annotated_path, format="JPEG", quality=92)

        meta = {
            "ts": now.isoformat(),
            "track_id": tracked.track_id,
            "cls_id": det.cls_id,
            "cls_name": det.cls_name,
            "confidence": det.conf,
            "bbox": [x1, y1, x2, y2],
            "route_label": category_name,
            "bin_index": int(mapping.bin_index),
            "uart_command": mapping.command,
            "image_path": str(raw_path),
            "annotated_path": str(annotated_path),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "image_path": str(raw_path),
            "annotated_path": str(annotated_path),
            "meta_path": str(meta_path),
            "route_label": category_name,
            "bin_index": int(mapping.bin_index),
        }

    def _mapping_for_detection(self, detection: Detection) -> ClassMapping:
        three_bin_command = parse_three_bin_class_name(detection.cls_name)
        if three_bin_command is not None:
            category = category_for_command(three_bin_command)
            if category is not None:
                return ClassMapping(
                    class_name=detection.cls_name,
                    command=category.code,
                    bin_index=category.bin_index,
                    enabled=True,
                )
        mapping = self._mapping.get(detection.cls_name)
        if mapping is not None:
            return _normalize_dispatch_mapping(mapping)
        fallback = self.cfg.unknown_fallback
        if detection.cls_name == fallback.class_name:
            return _normalize_dispatch_mapping(
                ClassMapping(
                    class_name=fallback.class_name,
                    command=fallback.command,
                    bin_index=fallback.bin_index,
                    enabled=True,
                )
            )
        category = category_for_class(detection.cls_name)
        return ClassMapping(
            class_name=detection.cls_name,
            command=category.code,
            bin_index=category.bin_index,
            enabled=True,
        )

    def _unknown_detection(
        self,
        frame_bgr: np.ndarray,
        raw: list[Detection],
        filtered: list[Detection],
    ) -> Detection | None:
        fallback = self.cfg.unknown_fallback
        if not fallback.enabled or filtered:
            return None
        return self._unknown_fallback.detect(
            frame_bgr,
            raw,
            class_name=fallback.class_name,
            roi_filter=self._in_roi,
            min_raw_confidence=fallback.min_raw_confidence,
            min_area_ratio=fallback.min_area_ratio,
            stable_frames=fallback.stable_frames,
            warmup_frames=fallback.warmup_frames,
        )

    def _apply_manual_references(
        self,
        frame_bgr: np.ndarray,
        detections: list[Detection],
    ) -> list[Detection]:
        recognizer = self._manual_reference_recognizer
        ref_cfg = self.cfg.manual_reference_recognition
        if recognizer is None or not ref_cfg.enabled:
            return detections
        fallback_name = self.cfg.unknown_fallback.class_name
        correctable_classes = {
            str(name).strip()
            for name in ref_cfg.correctable_yolo_classes
            if str(name).strip()
        }
        correction_targets = {
            str(name).strip()
            for name in ref_cfg.correction_target_classes
            if str(name).strip()
        }
        height, width = frame_bgr.shape[:2] if frame_bgr.ndim >= 2 else (0, 0)
        out: list[Detection] = []
        for detection in detections:
            mode = ""
            area_ratio = 0.0
            if detection.cls_name == fallback_name:
                mode = "unknown"
            elif detection.cls_name in correctable_classes:
                area_ratio = _box_area_ratio(detection.xyxy, width, height)
                if area_ratio >= ref_cfg.min_correction_area_ratio:
                    mode = "correction"
            if not mode:
                out.append(detection)
                continue
            match = recognizer.classify(frame_bgr, detection)
            if match is None:
                out.append(detection)
                continue
            if mode == "correction" and correction_targets and match.cls_name not in correction_targets:
                out.append(detection)
                continue
            out.append(
                Detection(
                    cls_id=match.cls_id,
                    cls_name=match.cls_name,
                    conf=max(detection.conf, match.similarity),
                    xyxy=detection.xyxy,
                    source="manual_reference",
                )
            )
            self.dispatch_status = f"manual reference {match.cls_name}"
            if mode == "correction":
                logger.info(
                    "manual reference corrected {} as {} similarity={:.3f} votes={} margin={:.3f} area={:.3f} backend={} source={}",
                    detection.cls_name,
                    match.cls_name,
                    match.similarity,
                    match.votes,
                    match.margin,
                    area_ratio,
                    match.backend,
                    match.image_path,
                )
            else:
                logger.info(
                    "manual reference matched unknown as {} similarity={:.3f} votes={} margin={:.3f} backend={} source={}",
                    match.cls_name,
                    match.similarity,
                    match.votes,
                    match.margin,
                    match.backend,
                    match.image_path,
                )
        return out

    def _apply_three_bin_classifier(
        self,
        frame_bgr: np.ndarray,
        detections: list[Detection],
    ) -> list[Detection]:
        classifier = self._three_bin_classifier
        cfg = self.cfg.three_bin_classifier
        if not cfg.enabled:
            return detections
        if cfg.mode == "route_consensus":
            return self._apply_route_consensus(frame_bgr, detections)
        if classifier is None:
            return detections
        fallback_name = self.cfg.unknown_fallback.class_name
        out: list[Detection] = []
        for detection in detections:
            if cfg.unknown_only and detection.cls_name != fallback_name:
                out.append(detection)
                continue
            prediction = classifier.classify_bgr(frame_bgr, detection.xyxy)
            if prediction is None or not prediction.passed:
                out.append(detection)
                continue
            out.append(
                Detection(
                    cls_id=prediction.cls_id,
                    cls_name=prediction.cls_name,
                    conf=max(detection.conf, prediction.confidence),
                    xyxy=detection.xyxy,
                    source=THREE_BIN_SOURCE,
                )
            )
            self.dispatch_status = f"Kaggle 3-bin {prediction.command}"
            logger.info(
                "three-bin classifier routed unknown as {} confidence={:.3f} margin={:.3f} backend={}",
                prediction.command,
                prediction.confidence,
                prediction.margin,
                prediction.backend,
            )
        return out

    def _apply_route_consensus(
        self,
        frame_bgr: np.ndarray,
        detections: list[Detection],
    ) -> list[Detection]:
        classifier = self._three_bin_classifier
        out: list[Detection] = []
        for detection in detections:
            primary_route = self._mapping_for_detection(detection).command
            prediction = (
                classifier.classify_bgr(frame_bgr, detection.xyxy)
                if classifier is not None
                else None
            )
            if prediction is None:
                out.append(
                    replace(
                        detection,
                        route_consensus="blocked",
                        route_consensus_reason="secondary classifier unavailable",
                    )
                )
                continue
            if not prediction.passed:
                out.append(
                    replace(
                        detection,
                        secondary_route=prediction.command,
                        secondary_confidence=prediction.confidence,
                        secondary_margin=prediction.margin,
                        route_consensus="blocked",
                        route_consensus_reason="secondary confidence or margin below gate",
                    )
                )
                continue
            passed = prediction.command == primary_route
            out.append(
                replace(
                    detection,
                    secondary_route=prediction.command,
                    secondary_confidence=prediction.confidence,
                    secondary_margin=prediction.margin,
                    route_consensus="passed" if passed else "blocked",
                    route_consensus_reason=(
                        ""
                        if passed
                        else f"route disagreement {primary_route}->{prediction.command}"
                    ),
                )
            )
        return out

    def process_frame(self, frame_bgr: np.ndarray, ts: datetime):
        raw = self.engine.predict(frame_bgr)
        threshold_for_detection = getattr(self.engine, "threshold_for_detection", None)
        filtered = [
            detection
            for detection in raw
            if detection.conf
            >= (
                float(threshold_for_detection(detection))
                if callable(threshold_for_detection)
                else self.cfg.model.conf_threshold
            )
        ]
        filtered_in_roi = [d for d in filtered if self._in_roi(d.xyxy)]
        unknown = self._unknown_detection(frame_bgr, raw, filtered_in_roi)
        if unknown is not None:
            filtered.append(unknown)
        filtered = self._apply_manual_references(frame_bgr, filtered)
        filtered = self._apply_three_bin_classifier(frame_bgr, filtered)
        self._save_low_conf_frame(frame_bgr, raw, ts)
        tracked = self.tracker.update(filtered)
        detections_for_render = [t.detection for t in tracked]
        now_mono = time.monotonic()
        roi_ready = self._roi_ready_for_dispatch(frame_bgr)
        roi_reference_boxes = tuple(
            t.detection.xyxy for t in tracked if self._in_roi(t.detection.xyxy)
        )
        foreground_multi = (
            evaluate_foreground_multi_object_dispatch(
                frame_bgr,
                roi=self.cfg.roi,
                max_objects=self.cfg.dispatch_guard.max_objects_per_dispatch,
                min_area_ratio=self.cfg.unknown_fallback.min_area_ratio,
                reference_boxes=roi_reference_boxes,
            )
            if roi_ready
            else None
        )
        if roi_ready and foreground_multi is not None and foreground_multi.allowed:
            frame_foreground_multi = evaluate_foreground_multi_object_dispatch(
                frame_bgr,
                roi=None,
                max_objects=self.cfg.dispatch_guard.max_objects_per_dispatch,
                min_area_ratio=max(self.cfg.unknown_fallback.min_area_ratio, 0.005),
                reference_boxes=tuple(t.detection.xyxy for t in tracked),
            )
            if not frame_foreground_multi.allowed:
                foreground_multi = frame_foreground_multi
        visible_in_roi = bool(
            roi_ready
            and (
                any(self._in_roi(t.detection.xyxy) for t in tracked)
                or (foreground_multi is not None and foreground_multi.object_count > 0)
            )
        )
        self._dispatch_guard.observe_frame(
            has_visible_object=visible_in_roi,
            roi_ready=roi_ready,
            now=now_mono,
        )
        self.dispatch_status = self._dispatch_guard.last_reason
        multi_class = evaluate_single_class_dispatch(
            tracked,
            in_roi=lambda xyxy: bool(roi_ready and self._in_roi(xyxy)),
            max_objects=self.cfg.dispatch_guard.max_objects_per_dispatch,
            max_classes=self.cfg.dispatch_guard.max_classes_per_dispatch,
        )
        if not multi_class.allowed:
            self.dispatch_status = multi_class.reason
            self._speak_multi_class_warning(multi_class.class_names)
            if not self._hardware_dispatch_enabled:
                for t in tracked:
                    self.tracker.mark_emitted(t.track_id)
            return detections_for_render
        if foreground_multi is not None and not foreground_multi.allowed:
            logger.debug(
                "foreground dispatch blocked objects={} references={} components={} unmatched={}",
                foreground_multi.object_count,
                foreground_multi.reference_count,
                foreground_multi.foreground_count,
                foreground_multi.unmatched_foreground_count,
            )
            self.dispatch_status = foreground_multi.reason
            self._speak_multi_class_warning(foreground_multi.class_names)
            if not self._hardware_dispatch_enabled:
                for t in tracked:
                    self.tracker.mark_emitted(t.track_id)
            return detections_for_render
        if (
            self.cfg.three_bin_classifier.enabled
            and self.cfg.three_bin_classifier.mode == "route_consensus"
        ):
            blocked_consensus = False
            for t in tracked:
                if t.detection.route_consensus == "passed":
                    continue
                if t.stable_frames < self.cfg.dispatch_guard.min_stable_frames:
                    continue
                blocked_consensus = True
                should_log = self.tracker.should_emit(t.track_id)
                self.tracker.mark_emitted(t.track_id)
                self.dispatch_status = (
                    t.detection.route_consensus_reason or "route consensus required"
                )
                if should_log:
                    try:
                        review_path = self._save_route_consensus_review(
                            frame_bgr,
                            t.detection,
                            ts,
                        )
                    except Exception as e:
                        review_path = "-"
                        logger.warning("route consensus review capture failed: {}", e)
                    logger.info(
                        "dispatch blocked route consensus track={} cls={} primary={} "
                        "secondary={} secondary_conf={} margin={} reason={} review={}",
                        t.track_id,
                        t.detection.cls_name,
                        self._mapping_for_detection(t.detection).command,
                        t.detection.secondary_route or "-",
                        t.detection.secondary_confidence,
                        t.detection.secondary_margin,
                        self.dispatch_status,
                        review_path,
                    )
            if blocked_consensus:
                return detections_for_render
        if not self._hardware_dispatch_enabled:
            self.dispatch_status = "TEST OFF"
            for t in tracked:
                self.tracker.mark_emitted(t.track_id)
            return detections_for_render
        for t in tracked:
            if self._unknown_dispatch_blocked(t.detection):
                should_log = self.tracker.should_emit(t.track_id)
                self.tracker.mark_emitted(t.track_id)
                self.dispatch_status = "unknown object review required"
                if should_log:
                    logger.info(
                        "dispatch blocked unknown object track={} conf={:.2f} source={}",
                        t.track_id,
                        t.detection.conf,
                        t.detection.source,
                    )
                continue
            if not self.tracker.should_emit(t.track_id):
                continue
            decision = self._dispatch_guard.evaluate(
                track_id=t.track_id,
                stable_frames=t.stable_frames,
                in_roi=bool(roi_ready and self._in_roi(t.detection.xyxy)),
                roi_ready=roi_ready,
                now=now_mono,
            )
            if not decision.allowed:
                self.dispatch_status = decision.reason
                continue
            if not self._foreground_changed_for_dispatch(frame_bgr, t.detection.xyxy):
                self.dispatch_status = "waiting foreground"
                continue
            mapping = self._mapping_for_detection(t.detection)
            owner_username = self.cfg.device.owner_username.strip()
            self.tracker.mark_emitted(t.track_id)
            category = category_for_command(mapping.command)
            capture: LabeledCapture = {
                "image_path": None,
                "annotated_path": None,
                "meta_path": None,
                "route_label": category.name if category is not None else f"Thùng {mapping.bin_index}",
                "bin_index": int(mapping.bin_index),
            }
            capture_ok = False
            try:
                capture = self._save_labeled_capture(frame_bgr, t, mapping)
                capture_ok = True
            except Exception as e:
                logger.warning("labeled capture failed; dispatch blocked: {}", e)
            thumb = _make_thumbnail(frame_bgr)
            row_id = self.history.insert(
                track_id=t.track_id,
                ts=ts,
                cls_id=t.detection.cls_id,
                cls_name=t.detection.cls_name,
                conf=t.detection.conf,
                bbox=t.detection.xyxy,
                thumbnail=thumb,
                image_path=capture["image_path"],
                annotated_path=capture["annotated_path"],
                meta_path=capture["meta_path"],
                route_label=capture["route_label"],
                bin_index=capture["bin_index"],
                uart_command=mapping.command,
                ack_status=(
                    "pending"
                    if capture_ok and self._has_uart()
                    else "uart_off"
                    if capture_ok
                    else "capture_failed"
                ),
                owner_account_id=_owner_account_id(owner_username),
                owner_username=owner_username or None,
                device_id=self.cfg.device.device_id.strip() or None,
            )
            if not capture_ok:
                logger.error(
                    "dispatch blocked because labeled capture failed track={} cls={} cmd={} bin={}",
                    t.track_id,
                    t.detection.cls_name,
                    mapping.command,
                    mapping.bin_index,
                )
                continue
            if self._has_uart():
                self._track_to_row[t.track_id] = row_id
                send_silent = None
                if computer_speaker_enabled(self.cfg):
                    send_silent = getattr(self.uart, "send_silent", None)
                    if not callable(send_silent):
                        self.history.update_ack(
                            row_id,
                            status="audio_route_unsupported",
                            rtt_ms=None,
                        )
                        self._track_to_row.pop(t.track_id, None)
                        logger.error(
                            "dispatch blocked because UART sender lacks SORTSILENT support "
                            "track={} cmd={}",
                            t.track_id,
                            mapping.command,
                        )
                        continue
                self._log_dispatch_evidence(
                    track_id=t.track_id,
                    cls_name=t.detection.cls_name,
                    command=mapping.command,
                    bin_index=int(mapping.bin_index),
                    confidence=t.detection.conf,
                    secondary_route=t.detection.secondary_route,
                    secondary_confidence=t.detection.secondary_confidence,
                    secondary_margin=t.detection.secondary_margin,
                )
                if computer_speaker_enabled(self.cfg):
                    self._speak_dispatch(
                        command=mapping.command,
                        bin_index=int(mapping.bin_index),
                        cls_name=t.detection.cls_name,
                        confidence=t.detection.conf,
                    )
                self._dispatch_guard.begin_dispatch(
                    track_id=t.track_id,
                    now=now_mono,
                    ack_timeout_seconds=self._ack_timeout_seconds(),
                )
                self.dispatch_status = self._dispatch_guard.last_reason
                if computer_speaker_enabled(self.cfg):
                    assert callable(send_silent)
                    send_silent(
                        track_id=t.track_id,
                        command=mapping.command,
                        conf=t.detection.conf,
                    )
                else:
                    self.uart.send(
                        track_id=t.track_id,
                        command=mapping.command,
                        conf=t.detection.conf,
                    )
            logger.info(
                "dispatch track={} cls={} cmd={} bin={} conf={:.2f}",
                t.track_id,
                t.detection.cls_name,
                mapping.command,
                mapping.bin_index,
                t.detection.conf,
            )
        return detections_for_render

    def _uart_payload_preview(self, command: str, confidence: float) -> str:
        try:
            return encode_sort(
                command,
                confidence,
                protocol=self.cfg.uart.protocol,
                silent=computer_speaker_enabled(self.cfg),
            ).decode("utf-8").strip()
        except Exception as e:
            return f"invalid:{e}"

    def _log_dispatch_evidence(
        self,
        *,
        track_id: int,
        cls_name: str,
        command: str,
        bin_index: int,
        confidence: float,
        secondary_route: str = "",
        secondary_confidence: float | None = None,
        secondary_margin: float | None = None,
    ) -> None:
        route = route_for_command(command)
        audio_event = f"sort_{command.strip().upper()[:1]}"
        laptop_audio_path = (
            sort_voice_path(command, self.cfg.speaker.voice_gender)
            if computer_speaker_enabled(self.cfg)
            else None
        )
        logger.info(
            "dispatch evidence send track={} cls={} cmd={} bin={} route={} "
            "secondary_route={} secondary_conf={} secondary_margin={} "
            "audio_mode={} audio_event={} hardware_audio_track={} voice_gender={} audio_file={} "
            "uart_protocol={} uart_payload={} ack_status=pending conf={:.2f}",
            track_id,
            cls_name,
            command,
            bin_index,
            route.label if route is not None else "-",
            secondary_route or "-",
            secondary_confidence,
            secondary_margin,
            self.cfg.speaker.output_mode,
            audio_event,
            route.gd5800_track if route is not None else "-",
            self.cfg.speaker.voice_gender,
            str(laptop_audio_path) if laptop_audio_path is not None else "-",
            self.cfg.uart.protocol,
            self._uart_payload_preview(command, confidence),
            confidence,
        )

    def _speak_multi_class_warning(self, class_names: tuple[str, ...]) -> None:
        text = normalize_multi_class_warning_text(self.cfg.dispatch_guard.multi_class_warning_text)
        cooldown = self.cfg.dispatch_guard.multi_class_warning_cooldown_seconds
        now = time.monotonic()
        if now - self._last_multi_class_warning_at < cooldown:
            return
        self._last_multi_class_warning_at = now
        track = self.cfg.dispatch_guard.multi_class_warning_audio_track
        use_computer_speaker = computer_speaker_enabled(self.cfg)
        try:
            audio_warning = getattr(self.uart, "send_audio_warning", None)
            if (
                not use_computer_speaker
                and self._hardware_dispatch_enabled
                and track > 0
                and self._has_uart()
                and callable(audio_warning)
            ):
                audio_warning(track)
            if use_computer_speaker:
                self.speaker.speak_text(
                    text=text,
                    key="multi_class_dispatch_blocked",
                    cooldown_seconds=cooldown,
                )
            logger.info("dispatch blocked multiple classes={}", ", ".join(class_names))
        except Exception as e:
            logger.warning("multi-class warning speaker failed: {}", e)

    def _speak_dispatch(
        self,
        *,
        command: str,
        bin_index: int,
        cls_name: str,
        confidence: float,
    ) -> None:
        try:
            self.speaker.speak(
                command=command,
                bin_index=bin_index,
                cls_name=cls_name,
                confidence=confidence,
            )
        except Exception as e:
            logger.warning("speaker dispatch failed: {}", e)

    def _unknown_dispatch_blocked(self, detection: Detection) -> bool:
        if parse_three_bin_class_name(detection.cls_name) is not None:
            return False
        if detection.cls_name in self._mapping:
            return False
        fallback = self.cfg.unknown_fallback
        if detection.cls_name != fallback.class_name:
            return category_for_known_class(detection.cls_name) is None
        if detection.cls_name in self._mapping:
            return False
        return not bool(fallback.dispatch_enabled)

    def on_ack(self, track_id: int, command: str, status: str, rtt_ms):
        self._dispatch_guard.complete_dispatch(track_id=track_id, now=time.monotonic())
        self.dispatch_status = self._dispatch_guard.last_reason
        row_id = self._track_to_row.pop(track_id, None)
        if row_id is None:
            return
        self.history.update_ack(row_id, status=status, rtt_ms=rtt_ms)
        logger.info(
            "dispatch evidence ack track={} history_id={} cmd={} ack_status={} rtt_ms={} state={}",
            track_id,
            row_id,
            command,
            status,
            rtt_ms,
            self._dispatch_guard.state,
        )
        self._track_to_speech.pop(track_id, None)

    def close(self):
        self.history.close()


def _owner_account_id(owner_username: str) -> int | None:
    if not owner_username:
        return None
    try:
        from app.agent.auth_service import AuthService

        for row in AuthService().list_accounts():
            if str(row.get("username")) == owner_username:
                return int(row["id"])
    except Exception:
        return None
    return None
