"""Pipeline orchestrator: frame -> infer -> track -> labeled capture -> history -> uart."""

from __future__ import annotations

import io
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.core.config import AppConfig, ClassMapping
from app.core.dispatch_guard import DispatchGuard
from app.core.events import Detection, TrackedDetection
from app.core.history import HistoryService
from app.core.manual_reference_recognition import ManualReferenceRecognizer
from app.core.speaker import NoopSpeaker, Speaker
from app.core.tracker import Tracker
from app.core.unknown_object_fallback import UnknownObjectFallback
from app.core.waste_categories import (
    category_for_class,
    category_for_command,
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


class _NoopUart:
    def send(self, track_id, command, conf) -> None:
        logger.debug(
            "uart disabled; skipped dispatch track={} cmd={} conf={:.2f}",
            track_id,
            command,
            conf,
        )


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
        self._manual_reference_recognizer = self._build_manual_reference_recognizer()
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
        self._dispatch_guard.reset()
        self.dispatch_status = self._dispatch_guard.last_reason

    def update_mappings(self, mappings):
        self._mapping = {m.class_name: m for m in mappings if m.enabled}

    def set_uart(self, uart) -> None:
        self.uart = uart if uart is not None else _NoopUart()

    def set_hardware_dispatch_enabled(self, enabled: bool) -> None:
        self._hardware_dispatch_enabled = bool(enabled)

    def set_dispatch_cooldown(self, seconds: float) -> None:
        self.cfg.dispatch_guard.min_sort_interval_seconds = max(0.0, float(seconds))
        self._configure_dispatch_guard()

    def set_min_dispatch_stable_frames(self, frames: int) -> None:
        self.cfg.dispatch_guard.min_stable_frames = max(1, int(frames))
        self._configure_dispatch_guard()

    def refresh_manual_references(self) -> None:
        if self._manual_reference_recognizer is not None:
            self._manual_reference_recognizer.refresh(force=True)

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
        if recognizer is None or not self.cfg.manual_reference_recognition.enabled:
            return detections
        fallback_name = self.cfg.unknown_fallback.class_name
        out: list[Detection] = []
        for detection in detections:
            if detection.cls_name != fallback_name:
                out.append(detection)
                continue
            match = recognizer.classify(frame_bgr, detection)
            if match is None:
                out.append(detection)
                continue
            out.append(
                Detection(
                    cls_id=match.cls_id,
                    cls_name=match.cls_name,
                    conf=max(detection.conf, match.similarity),
                    xyxy=detection.xyxy,
                )
            )
            self.dispatch_status = f"manual reference {match.cls_name}"
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

    def process_frame(self, frame_bgr: np.ndarray, ts: datetime):
        raw = self.engine.predict(frame_bgr)
        filtered = [d for d in raw if d.conf >= self.cfg.model.conf_threshold]
        filtered_in_roi = [d for d in filtered if self._in_roi(d.xyxy)]
        unknown = self._unknown_detection(frame_bgr, raw, filtered_in_roi)
        if unknown is not None:
            filtered.append(unknown)
        filtered = self._apply_manual_references(frame_bgr, filtered)
        self._save_low_conf_frame(frame_bgr, raw, ts)
        tracked = self.tracker.update(filtered)
        detections_for_render = [t.detection for t in tracked]
        now_mono = time.monotonic()
        roi_ready = self._roi_ready_for_dispatch(frame_bgr)
        visible_in_roi = bool(roi_ready and any(self._in_roi(t.detection.xyxy) for t in tracked))
        self._dispatch_guard.observe_frame(
            has_visible_object=visible_in_roi,
            roi_ready=roi_ready,
            now=now_mono,
        )
        self.dispatch_status = self._dispatch_guard.last_reason
        if not self._hardware_dispatch_enabled:
            self.dispatch_status = "TEST OFF"
            for t in tracked:
                self.tracker.mark_emitted(t.track_id)
            return detections_for_render
        for t in tracked:
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
                self._track_to_speech[t.track_id] = (
                    mapping.command,
                    int(mapping.bin_index),
                    t.detection.cls_name,
                    t.detection.conf,
                )
                self._dispatch_guard.begin_dispatch(
                    track_id=t.track_id,
                    now=now_mono,
                    ack_timeout_seconds=self._ack_timeout_seconds(),
                )
                self.dispatch_status = self._dispatch_guard.last_reason
                self.uart.send(track_id=t.track_id, command=mapping.command, conf=t.detection.conf)
            logger.info(
                "dispatch track={} cls={} cmd={} bin={} conf={:.2f}",
                t.track_id,
                t.detection.cls_name,
                mapping.command,
                mapping.bin_index,
                t.detection.conf,
            )
        return detections_for_render

    def on_ack(self, track_id: int, command: str, status: str, rtt_ms):
        self._dispatch_guard.complete_dispatch(track_id=track_id, now=time.monotonic())
        self.dispatch_status = self._dispatch_guard.last_reason
        row_id = self._track_to_row.pop(track_id, None)
        if row_id is None:
            return
        self.history.update_ack(row_id, status=status, rtt_ms=rtt_ms)
        speech = self._track_to_speech.pop(track_id, None)
        if status != "ok" or speech is None:
            return
        speech_command, bin_index, cls_name, confidence = speech
        try:
            self.speaker.speak(
                command=speech_command,
                bin_index=bin_index,
                cls_name=cls_name,
                confidence=confidence,
            )
        except Exception as e:
            logger.warning("speaker dispatch failed: {}", e)

    def close(self):
        self.history.close()
