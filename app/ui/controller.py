"""Glue between core workers and UI signals/slots."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal

from app.core.camera import CameraWorker
from app.core.config import AppConfig, save_config
from app.core.inference import InferenceEngine
from app.core.pipeline import Pipeline
from app.core.uart import UartWorker
from app.utils.logging import logger


class AppController(QObject):
    camera_status = Signal(bool)
    uart_status = Signal(bool)
    model_status = Signal(bool)
    frame_processed = Signal(object, list, float, float)

    def __init__(self, cfg: AppConfig, config_path: Path, db_path: Path):
        super().__init__()
        self.cfg = cfg
        self.config_path = config_path
        self.db_path = db_path
        self._engine: InferenceEngine | None = None
        self._camera: CameraWorker | None = None
        self._uart: UartWorker | None = None
        self._pipeline: Pipeline | None = None
        self._last_frame_t = 0.0
        self._fps = 0.0
        self._latency = 0.0

    def start(self) -> None:
        self._engine = InferenceEngine(
            self.cfg.model.path,
            device=self.cfg.model.device,
            conf=self.cfg.model.conf_threshold,
            iou=self.cfg.model.iou_threshold,
            imgsz=self.cfg.model.input_size,
            half=self.cfg.model.half_precision,
        )
        self.model_status.emit(True)

        self._uart = UartWorker(
            port=self.cfg.uart.port,
            baud=self.cfg.uart.baud,
            ack_timeout_ms=self.cfg.uart.ack_timeout_ms,
            auto_reconnect=self.cfg.uart.auto_reconnect,
        )
        self._uart.connected.connect(self.uart_status.emit)
        self._uart.start()

        self._pipeline = Pipeline(self.cfg, self._engine, self._uart, self.db_path)
        self._uart.ack_received.connect(self._pipeline.on_ack)

        self._camera = CameraWorker(
            source=self.cfg.camera.source,
            width=self.cfg.camera.width,
            height=self.cfg.camera.height,
            mirror=self.cfg.camera.mirror,
        )
        self._camera.connected.connect(self.camera_status.emit)
        self._camera.frame_ready.connect(self._on_frame)
        self._camera.start()
        logger.info("controller started")

    def _on_frame(self, frame: np.ndarray) -> None:
        if self._pipeline is None:
            return
        t0 = time.time()
        ts = datetime.now(timezone.utc)
        detections = self._pipeline.process_frame(frame, ts)
        self._latency = (time.time() - t0) * 1000
        if self._last_frame_t:
            inst_fps = 1.0 / max(time.time() - self._last_frame_t, 1e-6)
            self._fps = 0.9 * self._fps + 0.1 * inst_fps
        self._last_frame_t = time.time()
        self.frame_processed.emit(frame, detections, self._fps, self._latency)

    def update_config(self, new_cfg: AppConfig) -> None:
        self.cfg = new_cfg
        save_config(new_cfg, self.config_path)
        if self._engine is not None:
            self._engine.update_thresholds(
                new_cfg.model.conf_threshold, new_cfg.model.iou_threshold
            )
        if self._pipeline is not None:
            self._pipeline.update_mappings(new_cfg.mappings)
        logger.info("config updated")

    def stop(self) -> None:
        if self._camera is not None:
            self._camera.stop()
            self._camera.wait(2000)
        if self._uart is not None:
            self._uart.stop()
            self._uart.wait(2000)
        if self._pipeline is not None:
            self._pipeline.close()
        logger.info("controller stopped")
