"""Application config schema and atomic load/save."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

DEFAULT_UART_ACK_TIMEOUT_MS = 4500
MULTI_CLASS_WARNING_TEXT = "Chỉ đặt 1 vật trong khay. Đang thấy nhiều loại/vật nên không phân loại."


def normalize_multi_class_warning_text(_text: str) -> str:
    return MULTI_CLASS_WARNING_TEXT


class CameraConfig(BaseModel):
    source: str = ""
    width: int = 1280
    height: int = 720
    mirror: bool = False
    rotation: Literal[0, 90, 180, 270] = 0


class ModelConfig(BaseModel):
    path: str = "models/best.pt"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    conf_threshold: float = Field(0.4, ge=0.0, le=1.0)
    iou_threshold: float = Field(0.45, ge=0.0, le=1.0)
    input_size: int = 640
    half_precision: bool = False


class UartConfig(BaseModel):
    port: str = ""
    baud: int = 9600
    auto_reconnect: bool = True
    ack_timeout_ms: int = Field(DEFAULT_UART_ACK_TIMEOUT_MS, ge=10, le=5000)
    protocol: Literal["plain_group", "sort_line"] = "plain_group"


class DeviceConfig(BaseModel):
    device_id: str = "local-trash-sorter"
    device_name: str = "Trash Sorter Pro"
    location: str = "Local station"
    owner_username: str = ""


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
    mode: Literal["off", "manual", "auto_low_conf"] = "off"
    low_conf_threshold: float = Field(0.6, ge=0.0, le=1.0)
    output_dir: str = "dataset_v2"


class SpeakerConfig(BaseModel):
    enabled: bool = False
    output_mode: Literal["hardware", "computer_speaker"] = "hardware"
    voice_gender: Literal["female", "male"] = "female"
    cooldown_seconds: float = Field(2.5, ge=0.0, le=60.0)


class UnknownObjectFallbackConfig(BaseModel):
    enabled: bool = True
    class_name: str = "Unknown object"
    dispatch_enabled: bool = False
    command: str = Field("R", min_length=1, max_length=1)
    bin_index: int = Field(2, ge=1, le=9)
    min_raw_confidence: float = Field(0.05, ge=0.0, le=1.0)
    min_area_ratio: float = Field(0.003, ge=0.0001, le=0.5)
    stable_frames: int = Field(2, ge=1, le=10)
    warmup_frames: int = Field(6, ge=0, le=60)


class DispatchGuardConfig(BaseModel):
    min_sort_interval_seconds: float = Field(12.0, ge=0.0, le=300.0)
    busy_settle_seconds: float = Field(1.0, ge=0.0, le=30.0)
    min_stable_frames: int = Field(3, ge=1, le=30)
    empty_rearm_seconds: float = Field(2.0, ge=0.0, le=60.0)
    empty_rearm_frames: int = Field(10, ge=1, le=300)
    require_roi_for_dispatch: bool = True
    max_objects_per_dispatch: int = Field(1, ge=1, le=5)
    max_classes_per_dispatch: int = Field(1, ge=1, le=5)
    multi_class_warning_cooldown_seconds: float = Field(5.0, ge=0.0, le=120.0)
    multi_class_warning_text: str = MULTI_CLASS_WARNING_TEXT
    multi_class_warning_audio_track: int = Field(8, ge=0, le=8)


class ManualReferenceRecognitionConfig(BaseModel):
    enabled: bool = True
    min_similarity: float = Field(0.82, ge=0.0, le=1.0)
    min_consensus_similarity: float = Field(0.55, ge=0.0, le=1.0)
    min_margin: float = Field(0.04, ge=0.0, le=1.0)
    top_k: int = Field(5, ge=1, le=25)
    min_votes: int = Field(3, ge=1, le=25)
    max_references_per_class: int = Field(30, ge=1, le=500)
    cache_refresh_seconds: float = Field(30.0, ge=0.0, le=300.0)
    query_cache_seconds: float = Field(1.0, ge=0.0, le=30.0)
    correctable_yolo_classes: list[str] = Field(default_factory=lambda: ["Cardboard"])
    correction_target_classes: list[str] = Field(default_factory=lambda: ["Textile"])
    min_correction_area_ratio: float = Field(0.25, ge=0.0, le=1.0)


class ThreeBinClassifierConfig(BaseModel):
    enabled: bool = False
    model_path: str = "models/three_bin_classifier.pt"
    min_confidence: float = Field(0.72, ge=0.0, le=1.0)
    min_margin: float = Field(0.12, ge=0.0, le=1.0)
    unknown_only: bool = True
    min_crop_area_ratio: float = Field(0.003, ge=0.0, le=1.0)
    input_size: int = Field(224, ge=64, le=640)


def default_unknown_object_fallback_config() -> UnknownObjectFallbackConfig:
    return UnknownObjectFallbackConfig(
        enabled=True,
        class_name="Unknown object",
        dispatch_enabled=False,
        command="R",
        bin_index=2,
        min_raw_confidence=0.05,
        min_area_ratio=0.003,
        stable_frames=2,
        warmup_frames=6,
    )


def default_dispatch_guard_config() -> DispatchGuardConfig:
    return DispatchGuardConfig(
        min_sort_interval_seconds=12.0,
        busy_settle_seconds=1.0,
        min_stable_frames=3,
        empty_rearm_seconds=2.0,
        empty_rearm_frames=10,
        require_roi_for_dispatch=True,
        max_objects_per_dispatch=1,
        max_classes_per_dispatch=1,
        multi_class_warning_cooldown_seconds=5.0,
        multi_class_warning_text=MULTI_CLASS_WARNING_TEXT,
        multi_class_warning_audio_track=8,
    )


def default_manual_reference_recognition_config() -> ManualReferenceRecognitionConfig:
    return ManualReferenceRecognitionConfig(
        enabled=True,
        min_similarity=0.82,
        min_consensus_similarity=0.55,
        min_margin=0.04,
        top_k=5,
        min_votes=3,
        max_references_per_class=30,
        cache_refresh_seconds=30.0,
        query_cache_seconds=1.0,
        correctable_yolo_classes=["Cardboard"],
        correction_target_classes=["Textile"],
        min_correction_area_ratio=0.25,
    )


def default_three_bin_classifier_config() -> ThreeBinClassifierConfig:
    return ThreeBinClassifierConfig(
        enabled=False,
        model_path="models/three_bin_classifier.pt",
        min_confidence=0.72,
        min_margin=0.12,
        unknown_only=True,
        min_crop_area_ratio=0.003,
        input_size=224,
    )


class AppConfig(BaseModel):
    camera: CameraConfig = Field(default_factory=lambda: CameraConfig())
    model: ModelConfig = Field(
        default_factory=lambda: ModelConfig(conf_threshold=0.4, iou_threshold=0.45)
    )
    uart: UartConfig = Field(
        default_factory=lambda: UartConfig(ack_timeout_ms=DEFAULT_UART_ACK_TIMEOUT_MS)
    )
    device: DeviceConfig = Field(default_factory=lambda: DeviceConfig())
    mappings: list[ClassMapping] = Field(default_factory=list)
    roi: RoiConfig = Field(default_factory=lambda: RoiConfig())
    capture: CaptureConfig = Field(
        default_factory=lambda: CaptureConfig(low_conf_threshold=0.6)
    )
    speaker: SpeakerConfig = Field(
        default_factory=lambda: SpeakerConfig(
            enabled=False,
            output_mode="hardware",
            voice_gender="female",
            cooldown_seconds=2.5,
        )
    )
    unknown_fallback: UnknownObjectFallbackConfig = Field(
        default_factory=default_unknown_object_fallback_config
    )
    dispatch_guard: DispatchGuardConfig = Field(default_factory=default_dispatch_guard_config)
    manual_reference_recognition: ManualReferenceRecognitionConfig = Field(
        default_factory=default_manual_reference_recognition_config
    )
    three_bin_classifier: ThreeBinClassifierConfig = Field(
        default_factory=default_three_bin_classifier_config
    )
    theme: Literal["dark", "light"] = "dark"
    language: Literal["vi", "en"] = "vi"
    minimize_to_tray: bool = True
    autostart: bool = False


def computer_speaker_enabled(cfg: AppConfig) -> bool:
    return cfg.speaker.output_mode == "computer_speaker" and cfg.speaker.enabled


def normalize_speaker_output_config(cfg: AppConfig) -> AppConfig:
    clean = cfg.model_copy(deep=True)
    if clean.speaker.output_mode == "computer_speaker":
        clean.speaker.enabled = True
    else:
        clean.speaker.output_mode = "hardware"
        clean.speaker.enabled = False
    return clean


def startup_hardware_speaker_config(cfg: AppConfig) -> AppConfig:
    """Use hardware speaker as the app startup default while preserving voice choice."""
    clean = cfg.model_copy(deep=True)
    clean.speaker.output_mode = "hardware"
    clean.speaker.enabled = False
    return clean


def merge_missing_mappings(cfg: AppConfig, seed: AppConfig) -> tuple[AppConfig, bool]:
    """Add missing seed mappings without overwriting user-edited rows."""
    existing = {m.class_name for m in cfg.mappings}
    missing = [m for m in seed.mappings if m.class_name not in existing]
    if not missing:
        return cfg, False
    merged = cfg.model_copy(deep=True)
    merged.mappings = [*merged.mappings, *missing]
    return merged, True


def _load_example_config(current_path: Path) -> AppConfig | None:
    try:
        from app.utils.paths import example_config_path

        example = example_config_path()
        if example.resolve() == current_path.resolve() or not example.exists():
            return None
        return AppConfig.model_validate(json.loads(example.read_text(encoding="utf-8-sig")))
    except Exception:
        return None


def _repair_config(cfg: AppConfig, path: Path) -> tuple[AppConfig, bool]:
    changed = False
    if cfg.camera.source.strip() == "0":
        cfg.camera.source = ""
        changed = True
    if cfg.camera.rotation not in {0, 90, 180, 270}:
        cfg.camera.rotation = 0
        changed = True
    if cfg.uart.port.strip().upper() == "COM3" and not _is_usb_uart_port("COM3"):
        cfg.uart.port = ""
        changed = True
    if cfg.uart.protocol == "plain_group" and cfg.uart.ack_timeout_ms < 3000:
        cfg.uart.ack_timeout_ms = DEFAULT_UART_ACK_TIMEOUT_MS
        changed = True
    normalized_speaker = normalize_speaker_output_config(cfg)
    if normalized_speaker.speaker != cfg.speaker:
        cfg = normalized_speaker
        changed = True
    if cfg.manual_reference_recognition.cache_refresh_seconds == 3.0:
        cfg.manual_reference_recognition.cache_refresh_seconds = 30.0
        changed = True
    normalized_warning = normalize_multi_class_warning_text(
        cfg.dispatch_guard.multi_class_warning_text
    )
    if cfg.dispatch_guard.multi_class_warning_text != normalized_warning:
        cfg.dispatch_guard.multi_class_warning_text = normalized_warning
        changed = True
    seed = _load_example_config(path)
    if seed is not None:
        cfg, mappings_changed = merge_missing_mappings(cfg, seed)
        changed = changed or mappings_changed
    cfg, mappings_repaired = _repair_known_class_mappings(cfg)
    changed = changed or mappings_repaired
    return cfg, changed


def _missing_default_config_fields(raw: object) -> bool:
    if not isinstance(raw, dict):
        return False
    checks = (
        ("speaker", "voice_gender"),
        ("unknown_fallback", "dispatch_enabled"),
        ("dispatch_guard", "max_objects_per_dispatch"),
    )
    for section, key in checks:
        value = raw.get(section)
        if not isinstance(value, dict) or key not in value:
            return True
    return False


def _repair_known_class_mappings(cfg: AppConfig) -> tuple[AppConfig, bool]:
    try:
        from app.core.waste_categories import (
            category_for_known_class,
            normalize_mapping_to_three_bins,
        )
    except Exception:
        return cfg, False

    repaired: list[ClassMapping] = []
    changed = False
    for mapping in cfg.mappings:
        if category_for_known_class(mapping.class_name) is None:
            repaired.append(mapping)
            continue
        normalized = normalize_mapping_to_three_bins(mapping)
        changed = changed or normalized != mapping
        repaired.append(normalized)
    if not changed:
        return cfg, False
    out = cfg.model_copy(deep=True)
    out.mappings = repaired
    return out, True


def _is_usb_uart_port(port: str) -> bool:
    if not port:
        return False
    try:
        from app.utils.serial_enum import is_eligible_usb_serial_port, list_serial_ports
    except Exception:
        return False
    wanted = port.strip().upper()
    return any(
        str(p.get("device", "")).strip().upper() == wanted and is_eligible_usb_serial_port(p)
        for p in list_serial_ports()
    )


def save_config(cfg: AppConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    cfg = normalize_speaker_output_config(cfg)
    payload = cfg.model_dump(mode="json")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        cfg, _changed = _repair_config(AppConfig(), path)
        save_config(cfg, path)
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        missing_default_fields = _missing_default_config_fields(raw)
        cfg = AppConfig.model_validate(raw)
        cfg, changed = _repair_config(cfg, path)
        if changed or missing_default_fields:
            save_config(cfg, path)
        return cfg
    except Exception:
        backup = path.with_suffix(path.suffix + ".broken")
        shutil.copy2(path, backup)
        cfg, _changed = _repair_config(AppConfig(), path)
        save_config(cfg, path)
        return cfg
