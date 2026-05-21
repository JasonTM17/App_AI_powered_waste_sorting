"""YOLO inference wrapper around ultralytics."""

from __future__ import annotations

from pathlib import Path

from app.core.events import Detection
from app.utils.logging import logger


class InferenceEngine:
    def __init__(self, model_path, device="cpu", conf=0.4, iou=0.45, imgsz=640, half=False):
        from ultralytics import YOLO

        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"model not found: {path}")
        self._model = YOLO(str(path))
        self.class_names = dict(self._model.names)
        self.device = device
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.half = half
        logger.info(
            "inference loaded model={} classes={} device={}",
            str(path),
            len(self.class_names),
            device,
        )

    def predict(self, frame_bgr):
        results = self._model.predict(
            source=frame_bgr,
            conf=self.conf,
            iou=self.iou,
            imgsz=self.imgsz,
            device=self.device,
            half=self.half,
            verbose=False,
        )
        out = []
        if not results:
            return out
        r = results[0]
        if r.boxes is None or len(r.boxes) == 0:
            return out
        xyxy = r.boxes.xyxy.cpu().numpy().astype(int)
        confs = r.boxes.conf.cpu().numpy()
        clss = r.boxes.cls.cpu().numpy().astype(int)
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
