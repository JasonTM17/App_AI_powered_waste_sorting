"""YOLO inference wrapper around ultralytics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from app.core.config import SpecialistModelConfig
from app.core.events import Detection
from app.utils.logging import logger
from app.utils.paths import resource_path

YOLO_SPECIALIST_SOURCE = "YOLO specialist"


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception as e:
        logger.warning("cuda availability check failed: {}", e)
        return False


def resolve_inference_device(requested_device: str) -> tuple[str, str]:
    """Return the Ultralytics device value and a human-readable label."""
    requested = (requested_device or "auto").strip().lower()
    if requested == "cpu":
        return "cpu", "cpu"
    if requested in {"auto", "cuda"}:
        if _cuda_available():
            return "0", "cuda:0"
        if requested == "cuda":
            logger.warning("cuda requested but not available; falling back to cpu")
        return "cpu", "cpu"
    logger.warning("unknown inference device {}; falling back to auto", requested_device)
    if _cuda_available():
        return "0", "cuda:0"
    return "cpu", "cpu"


class InferenceEngine:
    RAW_CONF_FLOOR = 0.05

    def __init__(
        self,
        model_path,
        device="auto",
        conf=0.4,
        iou=0.45,
        imgsz=640,
        half=False,
        specialist: SpecialistModelConfig | None = None,
    ):
        from ultralytics import YOLO

        path = _resolve_model_path(model_path)
        self._model = YOLO(str(path))
        self.class_names = dict(self._model.names)
        self.requested_device = device
        self.device, self.device_label = resolve_inference_device(str(device))
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.half = bool(half and self.device != "cpu")
        self._specialist_model = None
        self._specialist_class_names: dict[int, str] = {}
        self._specialist_class_ids: list[int] = []
        self._specialist_thresholds: dict[str, float] = {}
        self._specialist_nms_iou = 0.7
        self._specialist_overlap_iou = 0.5
        self._load_specialist(specialist, YOLO)
        logger.info(
            "inference loaded model={} classes={} specialist_classes={} requested_device={} "
            "device={} half={} raw_conf={:.2f}",
            str(path),
            len(self.class_names),
            len(self._specialist_class_ids),
            device,
            self.device_label,
            self.half,
            self._predict_conf(),
        )

    def _load_specialist(self, cfg: SpecialistModelConfig | None, yolo_class: Any) -> None:
        if cfg is None or not cfg.enabled or not cfg.class_thresholds:
            return
        try:
            path = _resolve_model_path(cfg.path)
            model = yolo_class(str(path))
        except Exception as exc:
            logger.warning("YOLO specialist unavailable path={}: {}", cfg.path, exc)
            return
        names = {int(key): str(value) for key, value in dict(model.names).items()}
        wanted = set(cfg.class_thresholds)
        class_ids = sorted(class_id for class_id, name in names.items() if name in wanted)
        missing = sorted(wanted - {names[class_id] for class_id in class_ids})
        if missing:
            logger.warning("YOLO specialist missing configured classes: {}", ", ".join(missing))
        if not class_ids:
            return
        self._specialist_model = model
        self._specialist_class_names = names
        self._specialist_class_ids = class_ids
        self._specialist_thresholds = {
            name: float(cfg.class_thresholds[name])
            for name in wanted
            if name in names.values()
        }
        self._specialist_nms_iou = float(cfg.nms_iou)
        self._specialist_overlap_iou = float(cfg.overlap_iou)
        logger.info(
            "YOLO specialist loaded path={} classes={} thresholds={}",
            str(path),
            [names[class_id] for class_id in class_ids],
            self._specialist_thresholds,
        )

    def _predict_conf(self) -> float:
        return max(0.01, min(float(self.conf), self.RAW_CONF_FLOOR))

    def predict(self, frame_bgr):
        primary = self._predict_model(
            self._model,
            self.class_names,
            frame_bgr,
            conf=self._predict_conf(),
            source="YOLO",
        )
        if self._specialist_model is None:
            return primary
        specialist = self._predict_model(
            self._specialist_model,
            self._specialist_class_names,
            frame_bgr,
            conf=min(self._specialist_thresholds.values()),
            source=YOLO_SPECIALIST_SOURCE,
            classes=self._specialist_class_ids,
            iou=self._specialist_nms_iou,
        )
        specialist = [
            detection
            for detection in specialist
            if detection.conf >= self._specialist_thresholds.get(detection.cls_name, 1.0)
        ]
        return merge_specialist_detections(
            primary,
            specialist,
            primary_conf_threshold=float(self.conf),
            overlap_iou=self._specialist_overlap_iou,
        )

    def _predict_model(
        self,
        model: Any,
        class_names: dict[int, str],
        frame_bgr: Any,
        *,
        conf: float,
        source: str,
        classes: list[int] | None = None,
        iou: float | None = None,
    ) -> list[Detection]:
        results = model.predict(
            source=frame_bgr,
            conf=conf,
            iou=self.iou if iou is None else iou,
            imgsz=self.imgsz,
            device=self.device,
            half=self.half,
            classes=classes,
            verbose=False,
        )
        out: list[Detection] = []
        if not results:
            return out
        r = results[0]
        if r.boxes is None or len(r.boxes) == 0:
            return out
        boxes = cast(Any, r.boxes)
        xyxy = boxes.xyxy.cpu().numpy().astype(int)
        confs = boxes.conf.cpu().numpy()
        clss = boxes.cls.cpu().numpy().astype(int)
        for box, cf, ci in zip(xyxy, confs, clss, strict=True):
            x1, y1, x2, y2 = (int(v) for v in box)
            out.append(
                Detection(
                    cls_id=int(ci),
                    cls_name=class_names.get(int(ci), str(int(ci))),
                    conf=float(cf),
                    xyxy=(x1, y1, x2, y2),
                    source=source,
                )
            )
        return out

    def threshold_for_detection(self, detection: Detection) -> float:
        if detection.source == YOLO_SPECIALIST_SOURCE:
            return self._specialist_thresholds.get(detection.cls_name, 1.0)
        return float(self.conf)

    def update_thresholds(self, conf=None, iou=None):
        if conf is not None:
            self.conf = conf
        if iou is not None:
            self.iou = iou


def _resolve_model_path(model_path: str | Path) -> Path:
    path = Path(model_path)
    if path.exists():
        return path
    bundled = resource_path(path)
    if bundled.exists():
        return bundled
    raise FileNotFoundError(f"model not found: {model_path}")


def _bbox_iou(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> float:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(
        0, min(ay2, by2) - max(ay1, by1)
    )
    first_area = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    second_area = max(0, bx2 - bx1) * max(0, by2 - by1)
    return intersection / max(first_area + second_area - intersection, 1)


def merge_specialist_detections(
    primary: list[Detection],
    specialist: list[Detection],
    *,
    primary_conf_threshold: float,
    overlap_iou: float,
) -> list[Detection]:
    accepted: list[Detection] = []
    for detection in sorted(specialist, key=lambda item: item.conf, reverse=True):
        overlaps_primary = any(
            item.conf >= primary_conf_threshold
            and _bbox_iou(item.xyxy, detection.xyxy) >= overlap_iou
            for item in primary
        )
        overlaps_specialist = any(
            _bbox_iou(item.xyxy, detection.xyxy) >= overlap_iou for item in accepted
        )
        if not overlaps_primary and not overlaps_specialist:
            accepted.append(detection)
    return [*primary, *accepted]
