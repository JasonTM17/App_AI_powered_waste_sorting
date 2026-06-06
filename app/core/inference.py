"""YOLO inference wrapper around ultralytics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from app.core.events import Detection
from app.utils.logging import logger
from app.utils.paths import resource_path


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

    def __init__(self, model_path, device="auto", conf=0.4, iou=0.45, imgsz=640, half=False):
        from ultralytics import YOLO

        path = Path(model_path)
        if not path.exists():
            bundled = resource_path(path)
            if bundled.exists():
                path = bundled
            else:
                raise FileNotFoundError(f"model not found: {model_path}")
        self._model = YOLO(str(path))
        self.class_names = dict(self._model.names)
        self.requested_device = device
        self.device, self.device_label = resolve_inference_device(str(device))
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.half = bool(half and self.device != "cpu")
        logger.info(
            "inference loaded model={} classes={} requested_device={} device={} half={} raw_conf={:.2f}",
            str(path),
            len(self.class_names),
            device,
            self.device_label,
            self.half,
            self._predict_conf(),
        )

    def _predict_conf(self) -> float:
        return max(0.01, min(float(self.conf), self.RAW_CONF_FLOOR))

    def predict(self, frame_bgr):
        results = self._model.predict(
            source=frame_bgr,
            conf=self._predict_conf(),
            iou=self.iou,
            imgsz=self.imgsz,
            device=self.device,
            half=self.half,
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
                    cls_name=self.class_names.get(int(ci), str(int(ci))),
                    conf=float(cf),
                    xyxy=(x1, y1, x2, y2),
                )
            )
        return out

    def update_thresholds(self, conf=None, iou=None):
        if conf is not None:
            self.conf = conf
        if iou is not None:
            self.iou = iou
