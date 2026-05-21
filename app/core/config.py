"""Application config schema and atomic load/save."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class CameraConfig(BaseModel):
    source: str = "0"
    width: int = 1280
    height: int = 720
    mirror: bool = False


class ModelConfig(BaseModel):
    path: str = "models/best.pt"
    device: Literal["cpu", "cuda"] = "cpu"
    conf_threshold: float = Field(0.4, ge=0.0, le=1.0)
    iou_threshold: float = Field(0.45, ge=0.0, le=1.0)
    input_size: int = 640
    half_precision: bool = False


class UartConfig(BaseModel):
    port: str = "COM3"
    baud: int = 9600
    auto_reconnect: bool = True
    ack_timeout_ms: int = Field(200, ge=10, le=5000)


class ClassMapping(BaseModel):
    class_name: str
    command: str = Field(..., min_length=1, max_length=1)
    bin_index: int = Field(..., ge=1, le=9)
    enabled: bool = True


class RoiConfig(BaseModel):
    enabled: bool = False
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


class CaptureConfig(BaseModel):
    mode: Literal["off", "manual", "auto_low_conf"] = "auto_low_conf"
    low_conf_threshold: float = Field(0.6, ge=0.0, le=1.0)
    output_dir: str = "dataset_v2"


class AppConfig(BaseModel):
    camera: CameraConfig = CameraConfig()
    model: ModelConfig = ModelConfig()
    uart: UartConfig = UartConfig()
    mappings: list[ClassMapping] = Field(default_factory=list)
    roi: RoiConfig = RoiConfig()
    capture: CaptureConfig = CaptureConfig()
    theme: Literal["dark", "light"] = "dark"
    language: Literal["vi", "en"] = "vi"
    minimize_to_tray: bool = True
    autostart: bool = False


def save_config(cfg: AppConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = cfg.model_dump(mode="json")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        cfg = AppConfig()
        save_config(cfg, path)
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig.model_validate(raw)
    except Exception:
        backup = path.with_suffix(path.suffix + ".broken")
        shutil.copy2(path, backup)
        cfg = AppConfig()
        save_config(cfg, path)
        return cfg
