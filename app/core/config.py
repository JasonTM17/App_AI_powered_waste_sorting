"""Application config schema and atomic load/save."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.utils.paths import resolve_data_path, resource_path

DEFAULT_UART_ACK_TIMEOUT_MS = 4500
MANUAL_REFERENCE_CORRECTION_CLASSES = (
    "Aerosols",
    "Aluminum can",
    "Aluminum caps",
    "Cardboard",
    "Cellulose",
    "Ceramic",
    "Combined plastic",
    "Container for household chemicals",
    "Disposable tableware",
    "Electronics",
    "Foil",
    "Furniture",
    "Glass bottle",
    "Iron utensils",
    "Liquid",
    "Metal shavings",
    "Milk bottle",
    "Organic",
    "Paper",
    "Paper bag",
    "Paper cups",
    "Paper shavings",
    "Papier mache",
    "Plastic bag",
    "Plastic bottle",
    "Plastic can",
    "Plastic canister",
    "Plastic caps",
    "Plastic cup",
    "Plastic shaker",
    "Plastic shavings",
    "Plastic toys",
    "Postal packaging",
    "Printing industry",
    "Scrap metal",
    "Stretch film",
    "Tetra pack",
    "Textile",
    "Tin",
    "Unknown plastic",
    "Wood",
    "Zip plastic bag",
    "Pen",
    "Battery",
    "Toothbrush",
)
MULTI_CLASS_WARNING_TEXT = "Chỉ đặt 1 vật trong khay. Đang thấy nhiều loại/vật nên không phân loại."


def normalize_multi_class_warning_text(_text: str) -> str:
    return MULTI_CLASS_WARNING_TEXT


class CameraConfig(BaseModel):
    source: str = ""
    width: int = 1280
    height: int = 720
    mirror: bool = False
    rotation: Literal[0, 90, 180, 270] = 0


class SpecialistClassRouteConfig(BaseModel):
    parent_class: str
    operator_label: str
    hazardous: bool = False


def default_specialist_class_routes() -> dict[str, SpecialistClassRouteConfig]:
    rows = {
        "Comb": ("Unknown plastic", "Cái lược", False),
        "Marker": ("Pen", "Bút dạ", False),
        "Lighter": ("Unknown plastic", "Bật lửa", False),
        "Battery AA AAA": ("Battery", "Pin AA/AAA", True),
        "Battery 9V": ("Battery", "Pin 9V", True),
        "Power socket": ("Electronics", "Ổ cắm điện", False),
        "Wall charger": ("Electronics", "Cục sạc", False),
        "Charging cable": ("Electronics", "Dây sạc", False),
        "Plastic bag": ("Plastic bag", "Bì ni lông", False),
        "Eggshell": ("Organic", "Vỏ trứng gà", False),
    }
    return {
        name: SpecialistClassRouteConfig(
            parent_class=parent_class,
            operator_label=operator_label,
            hazardous=hazardous,
        )
        for name, (parent_class, operator_label, hazardous) in rows.items()
    }


class SpecialistModelConfig(BaseModel):
    enabled: bool = True
    path: str = "models/new-class-specialist.pt"
    class_thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "Pen": 0.35,
            "Battery": 0.30,
            "Toothbrush": 0.25,
        }
    )
    class_routes: dict[str, SpecialistClassRouteConfig] = Field(
        default_factory=default_specialist_class_routes
    )
    min_aspect_ratios: dict[str, float] = Field(
        default_factory=lambda: {
            "Pen": 2.2,
            "Toothbrush": 2.0,
        }
    )
    nms_iou: float = Field(0.7, ge=0.0, le=1.0)
    overlap_iou: float = Field(0.5, ge=0.0, le=1.0)

    @field_validator("class_thresholds")
    @classmethod
    def validate_class_thresholds(cls, value: dict[str, float]) -> dict[str, float]:
        clean: dict[str, float] = {}
        for raw_name, raw_threshold in value.items():
            name = str(raw_name).strip()
            threshold = float(raw_threshold)
            if not name:
                raise ValueError("specialist class names must not be empty")
            if not 0.0 <= threshold <= 1.0:
                raise ValueError("specialist class thresholds must be between 0 and 1")
            clean[name] = threshold
        return clean

    @field_validator("min_aspect_ratios")
    @classmethod
    def validate_min_aspect_ratios(cls, value: dict[str, float]) -> dict[str, float]:
        clean: dict[str, float] = {}
        for raw_name, raw_ratio in value.items():
            name = str(raw_name).strip()
            ratio = float(raw_ratio)
            if not name:
                raise ValueError("specialist shape class names must not be empty")
            if ratio < 1.0:
                raise ValueError("specialist minimum aspect ratios must be at least 1")
            clean[name] = ratio
        return clean


class ModelConfig(BaseModel):
    path: str = "models/best.pt"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    conf_threshold: float = Field(0.4, ge=0.0, le=1.0)
    class_thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "Organic": 0.25,
            "Plastic bag": 0.16,
            "Plastic bottle": 0.30,
            "Glass bottle": 0.45,
            "Milk bottle": 0.30,
            "Pen": 0.35,
        }
    )
    iou_threshold: float = Field(0.45, ge=0.0, le=1.0)
    input_size: int = 640
    half_precision: bool = True
    specialist: SpecialistModelConfig = Field(default_factory=SpecialistModelConfig)

    @field_validator("class_thresholds")
    @classmethod
    def validate_class_thresholds(cls, value: dict[str, float]) -> dict[str, float]:
        clean: dict[str, float] = {}
        for raw_name, raw_threshold in value.items():
            name = str(raw_name).strip()
            threshold = float(raw_threshold)
            if not name:
                raise ValueError("model class names must not be empty")
            if not 0.0 <= threshold <= 1.0:
                raise ValueError("model class thresholds must be between 0 and 1")
            clean[name] = threshold
        return clean


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


def default_tray_roi_for_camera(width: int, height: int) -> RoiConfig:
    """Return the calibrated white-tray crop scaled to the camera resolution."""
    base_w = 960
    return RoiConfig(
        enabled=True,
        x=max(0, round(32 * width / base_w)),
        y=0,
        width=max(1, round(875 * width / base_w)),
        height=max(1, height),
    )


class CaptureConfig(BaseModel):
    mode: Literal["off", "manual", "auto_low_conf"] = "off"
    low_conf_threshold: float = Field(0.6, ge=0.0, le=1.0)
    output_dir: str = "dataset_v2"


class AutoReviewQueueConfig(BaseModel):
    enabled: bool = False
    cooldown_seconds: float = Field(12.0, ge=1.0, le=300.0)
    capture_low_confidence: bool = False
    capture_unknown: bool = False
    capture_multiple_objects: bool = False
    capture_visual_safety: bool = False


class HazardousWasteConfig(BaseModel):
    battery_warning_hold_seconds: float = Field(8.0, ge=1.0, le=120.0)
    confirmation_window_seconds: float = Field(10.0, ge=1.0, le=120.0)
    battery_command: str = Field("R", min_length=1, max_length=1)
    battery_bin_index: int = Field(2, ge=1, le=9)


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
    min_sort_interval_seconds: float = Field(2.0, ge=0.0, le=300.0)
    busy_settle_seconds: float = Field(2.0, ge=0.0, le=30.0)
    min_stable_frames: int = Field(2, ge=1, le=30)
    empty_rearm_seconds: float = Field(1.0, ge=0.0, le=60.0)
    empty_rearm_frames: int = Field(6, ge=1, le=300)
    require_roi_for_dispatch: bool = True
    max_objects_per_dispatch: int = Field(1, ge=1, le=5)
    max_classes_per_dispatch: int = Field(1, ge=1, le=5)
    min_dispatch_confidence: float = Field(0.0, ge=0.0, le=1.0)
    max_dispatch_bbox_area_ratio: float = Field(1.0, ge=0.1, le=1.0)
    min_dispatch_sharpness: float = Field(0.0, ge=0.0, le=1000.0)
    multi_class_warning_cooldown_seconds: float = Field(5.0, ge=0.0, le=120.0)
    multi_class_warning_text: str = MULTI_CLASS_WARNING_TEXT
    multi_class_warning_audio_track: int = Field(8, ge=0, le=8)


class ManualReferenceRecognitionConfig(BaseModel):
    enabled: bool = True
    allow_unknown_matches: bool = True
    min_similarity: float = Field(0.88, ge=0.0, le=1.0)
    unknown_min_similarity: float = Field(0.92, ge=0.0, le=1.0)
    organic_unknown_min_similarity: float = Field(0.65, ge=0.0, le=1.0)
    min_consensus_similarity: float = Field(0.72, ge=0.0, le=1.0)
    min_margin: float = Field(0.08, ge=0.0, le=1.0)
    top_k: int = Field(7, ge=1, le=25)
    min_votes: int = Field(4, ge=1, le=25)
    unknown_min_votes: int = Field(1, ge=1, le=25)
    organic_unknown_min_votes: int = Field(7, ge=1, le=25)
    max_references_per_class: int = Field(60, ge=1, le=500)
    cache_refresh_seconds: float = Field(30.0, ge=0.0, le=300.0)
    query_cache_seconds: float = Field(5.0, ge=0.0, le=30.0)
    correctable_yolo_classes: list[str] = Field(
        default_factory=lambda: list(MANUAL_REFERENCE_CORRECTION_CLASSES)
    )
    correction_target_classes: list[str] = Field(
        default_factory=lambda: list(MANUAL_REFERENCE_CORRECTION_CLASSES)
    )
    correction_targets_by_yolo_class: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "Cardboard": ["Textile", "Organic"],
            "Glass bottle": ["Iron utensils", "Wood"],
            "Pen": ["Disposable tableware", "Iron utensils", "Electronics"],
            "Plastic cup": ["Organic", "Iron utensils"],
            "Plastic bottle": ["Organic"],
            "Aluminum can": ["Plastic bottle"],
            "Ceramic": ["Plastic bottle", "Glass bottle", "Iron utensils"],
        }
    )
    min_correction_area_ratio: float = Field(0.25, ge=0.0, le=1.0)
    max_correction_confidence: float = Field(0.90, ge=0.0, le=1.0)


class ThreeBinClassifierConfig(BaseModel):
    enabled: bool = False
    model_path: str = "models/three_bin_classifier.pt"
    mode: Literal["unknown_only", "route_consensus"] = "unknown_only"
    min_confidence: float = Field(0.72, ge=0.0, le=1.0)
    min_margin: float = Field(0.12, ge=0.0, le=1.0)
    unknown_only: bool = True
    max_primary_confidence: float = Field(0.0, ge=0.0, le=1.0)
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
        min_sort_interval_seconds=0.0,
        busy_settle_seconds=0.0,
        min_stable_frames=1,
        empty_rearm_seconds=0.0,
        empty_rearm_frames=1,
        require_roi_for_dispatch=True,
        max_objects_per_dispatch=1,
        max_classes_per_dispatch=1,
        min_dispatch_confidence=0.0,
        max_dispatch_bbox_area_ratio=1.0,
        min_dispatch_sharpness=0.0,
        multi_class_warning_cooldown_seconds=5.0,
        multi_class_warning_text=MULTI_CLASS_WARNING_TEXT,
        multi_class_warning_audio_track=8,
    )


def default_manual_reference_recognition_config() -> ManualReferenceRecognitionConfig:
    return ManualReferenceRecognitionConfig(
        enabled=True,
        allow_unknown_matches=True,
        min_similarity=0.88,
        unknown_min_similarity=0.92,
        organic_unknown_min_similarity=0.65,
        min_consensus_similarity=0.72,
        min_margin=0.08,
        top_k=7,
        min_votes=4,
        unknown_min_votes=1,
        organic_unknown_min_votes=7,
        max_references_per_class=60,
        cache_refresh_seconds=30.0,
        query_cache_seconds=5.0,
        correctable_yolo_classes=list(MANUAL_REFERENCE_CORRECTION_CLASSES),
        correction_target_classes=list(MANUAL_REFERENCE_CORRECTION_CLASSES),
        min_correction_area_ratio=0.25,
        max_correction_confidence=0.90,
    )


def default_three_bin_classifier_config() -> ThreeBinClassifierConfig:
    return ThreeBinClassifierConfig(
        enabled=False,
        model_path="models/three_bin_classifier.pt",
        mode="unknown_only",
        min_confidence=0.72,
        min_margin=0.12,
        unknown_only=True,
        max_primary_confidence=0.0,
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
    capture: CaptureConfig = Field(default_factory=lambda: CaptureConfig(low_conf_threshold=0.6))
    auto_review_queue: AutoReviewQueueConfig = Field(default_factory=AutoReviewQueueConfig)
    hazardous_waste: HazardousWasteConfig = Field(default_factory=HazardousWasteConfig)
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
    minimize_to_tray: bool = False
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
    """Normalize the persisted speaker choice without overriding the operator."""
    return normalize_speaker_output_config(cfg)


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
    def _runtime_file_exists(value: str) -> bool:
        candidate = Path(str(value or "")).expanduser()
        return any(
            item.exists() and item.is_file()
            for item in (candidate, resource_path(candidate), resolve_data_path(candidate))
        )

    if not _runtime_file_exists(cfg.model.path):
        bundled_primary = resource_path("models/best.pt")
        if bundled_primary.exists():
            cfg.model.path = "models/best.pt"
            changed = True
    legacy_primary_models = {
        "models/best.pt",
        "models/manual-capture-20260612-candidate.pt",
    }
    balanced_primary = "models/real-camera-balanced-20260619-candidate.pt"
    if cfg.model.path.replace("\\", "/") in legacy_primary_models and _runtime_file_exists(
        balanced_primary
    ):
        cfg.model.path = balanced_primary
        changed = True
    if cfg.model.specialist.enabled and not _runtime_file_exists(cfg.model.specialist.path):
        bundled_specialist = resource_path("models/new-class-specialist.pt")
        if bundled_specialist.exists():
            cfg.model.specialist.path = "models/new-class-specialist.pt"
            changed = True
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
    if (
        not cfg.roi.enabled
        or cfg.roi.width <= 0
        or cfg.roi.height <= 0
        or cfg.roi.x < 0
        or cfg.roi.y < 0
        or cfg.roi.x + cfg.roi.width > cfg.camera.width
        or cfg.roi.y + cfg.roi.height > cfg.camera.height
    ):
        cfg.roi = default_tray_roi_for_camera(cfg.camera.width, cfg.camera.height)
        changed = True
    normalized_speaker = normalize_speaker_output_config(cfg)
    if normalized_speaker.speaker != cfg.speaker:
        cfg = normalized_speaker
        changed = True
    if cfg.manual_reference_recognition.cache_refresh_seconds == 3.0:
        cfg.manual_reference_recognition.cache_refresh_seconds = 30.0
        changed = True
    if cfg.manual_reference_recognition.query_cache_seconds == 1.0:
        cfg.manual_reference_recognition.query_cache_seconds = 5.0
        changed = True
    if cfg.manual_reference_recognition.max_references_per_class == 30:
        cfg.manual_reference_recognition.max_references_per_class = 60
        changed = True
    if cfg.dispatch_guard.min_sort_interval_seconds != 0.0:
        cfg.dispatch_guard.min_sort_interval_seconds = 0.0
        changed = True
    if cfg.dispatch_guard.busy_settle_seconds != 0.0:
        cfg.dispatch_guard.busy_settle_seconds = 0.0
        changed = True
    if cfg.dispatch_guard.empty_rearm_seconds != 0.0:
        cfg.dispatch_guard.empty_rearm_seconds = 0.0
        changed = True
    if cfg.dispatch_guard.empty_rearm_frames != 1:
        cfg.dispatch_guard.empty_rearm_frames = 1
        changed = True
    if cfg.dispatch_guard.min_stable_frames != 1:
        cfg.dispatch_guard.min_stable_frames = 1
        changed = True
    if cfg.auto_review_queue.cooldown_seconds < 12.0:
        cfg.auto_review_queue.cooldown_seconds = 12.0
        changed = True
    if cfg.auto_review_queue.enabled:
        cfg.auto_review_queue.enabled = False
        changed = True
    if cfg.auto_review_queue.capture_low_confidence:
        cfg.auto_review_queue.capture_low_confidence = False
        changed = True
    if cfg.auto_review_queue.capture_unknown:
        cfg.auto_review_queue.capture_unknown = False
        changed = True
    if cfg.auto_review_queue.capture_multiple_objects:
        cfg.auto_review_queue.capture_multiple_objects = False
        changed = True
    if cfg.auto_review_queue.capture_visual_safety:
        cfg.auto_review_queue.capture_visual_safety = False
        changed = True
    # Once a known mapped class is recognized, confidence no longer blocks the
    # hardware command. Normalize persisted values so UI/config reflects it.
    if cfg.dispatch_guard.min_dispatch_confidence != 0.0:
        cfg.dispatch_guard.min_dispatch_confidence = 0.0
        changed = True
    if cfg.dispatch_guard.max_dispatch_bbox_area_ratio <= 0.82:
        cfg.dispatch_guard.max_dispatch_bbox_area_ratio = 1.0
        changed = True
    if not cfg.manual_reference_recognition.allow_unknown_matches:
        cfg.manual_reference_recognition.allow_unknown_matches = True
        changed = True
    if cfg.manual_reference_recognition.unknown_min_similarity < 0.92:
        cfg.manual_reference_recognition.unknown_min_similarity = 0.92
        changed = True
    if cfg.manual_reference_recognition.max_correction_confidence < 0.90:
        cfg.manual_reference_recognition.max_correction_confidence = 0.90
        changed = True
    legacy_thresholds = {
        "Plastic bottle": 0.08,
        "Glass bottle": 0.10,
        "Milk bottle": 0.10,
    }
    for class_name, old_threshold in legacy_thresholds.items():
        if cfg.model.class_thresholds.get(class_name) == old_threshold:
            cfg.model.class_thresholds[class_name] = 0.30
            changed = True
    if "Organic" not in cfg.model.class_thresholds:
        cfg.model.class_thresholds["Organic"] = 0.25
        changed = True
    if cfg.model.class_thresholds.get("Plastic bag") != 0.16:
        cfg.model.class_thresholds["Plastic bag"] = 0.16
        changed = True
    if cfg.model.class_thresholds.get("Glass bottle", 1.0) < 0.45:
        cfg.model.class_thresholds["Glass bottle"] = 0.45
        changed = True
    if cfg.model.class_thresholds.get("Pen") != 0.35:
        cfg.model.class_thresholds["Pen"] = 0.35
        changed = True
    if cfg.model.specialist.class_thresholds.get("Pen") != 0.35:
        cfg.model.specialist.class_thresholds["Pen"] = 0.35
        changed = True
    if cfg.three_bin_classifier.min_confidence <= 0.42:
        cfg.three_bin_classifier.min_confidence = 0.72
        changed = True
    if cfg.three_bin_classifier.min_margin <= 0.10:
        cfg.three_bin_classifier.min_margin = 0.12
        changed = True
    if cfg.three_bin_classifier.max_primary_confidence >= 0.70:
        cfg.three_bin_classifier.max_primary_confidence = 0.45
        changed = True
    legacy_reference_values = (
        cfg.manual_reference_recognition.min_similarity <= 0.82
        and cfg.manual_reference_recognition.min_consensus_similarity <= 0.55
        and cfg.manual_reference_recognition.min_margin <= 0.04
    )
    if legacy_reference_values:
        cfg.manual_reference_recognition.min_similarity = 0.88
        cfg.manual_reference_recognition.min_consensus_similarity = 0.72
        cfg.manual_reference_recognition.min_margin = 0.08
        cfg.manual_reference_recognition.top_k = 7
        cfg.manual_reference_recognition.min_votes = 4
        changed = True
    required_correctable = MANUAL_REFERENCE_CORRECTION_CLASSES
    for class_name in required_correctable:
        if class_name not in cfg.manual_reference_recognition.correctable_yolo_classes:
            cfg.manual_reference_recognition.correctable_yolo_classes.append(class_name)
            changed = True
    required_targets = MANUAL_REFERENCE_CORRECTION_CLASSES
    for class_name in required_targets:
        if class_name not in cfg.manual_reference_recognition.correction_target_classes:
            cfg.manual_reference_recognition.correction_target_classes.append(class_name)
            changed = True
    required_targets_by_source = {
        "Cardboard": ["Textile", "Organic"],
        "Glass bottle": ["Iron utensils", "Wood"],
        "Pen": ["Disposable tableware", "Iron utensils", "Electronics"],
        "Plastic cup": ["Organic", "Iron utensils"],
        "Plastic bottle": ["Organic"],
        "Aluminum can": ["Plastic bottle"],
        "Ceramic": ["Plastic bottle", "Glass bottle", "Iron utensils"],
    }
    target_map = cfg.manual_reference_recognition.correction_targets_by_yolo_class
    for source_class, target_classes in required_targets_by_source.items():
        configured_targets = target_map.setdefault(source_class, [])
        for target_class in target_classes:
            if target_class not in configured_targets:
                configured_targets.append(target_class)
                changed = True
    normalized_warning = normalize_multi_class_warning_text(
        cfg.dispatch_guard.multi_class_warning_text
    )
    if cfg.dispatch_guard.multi_class_warning_text != normalized_warning:
        cfg.dispatch_guard.multi_class_warning_text = normalized_warning
        changed = True
    expected_unknown_only = cfg.three_bin_classifier.mode == "unknown_only"
    if cfg.three_bin_classifier.unknown_only != expected_unknown_only:
        cfg.three_bin_classifier.unknown_only = expected_unknown_only
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
        ("model", "specialist"),
        ("speaker", "voice_gender"),
        ("unknown_fallback", "dispatch_enabled"),
        ("dispatch_guard", "max_objects_per_dispatch"),
        ("dispatch_guard", "min_dispatch_confidence"),
        ("manual_reference_recognition", "allow_unknown_matches"),
        ("manual_reference_recognition", "correction_targets_by_yolo_class"),
        ("three_bin_classifier", "mode"),
    )
    for section, key in checks:
        value = raw.get(section)
        if not isinstance(value, dict) or key not in value:
            return True
    return False


def _migrate_three_bin_classifier_mode(raw: object) -> bool:
    if not isinstance(raw, dict):
        return False
    section = raw.get("three_bin_classifier")
    if not isinstance(section, dict) or "mode" in section:
        return False
    section["mode"] = "route_consensus" if section.get("unknown_only") is False else "unknown_only"
    return True


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
        migrated_mode = _migrate_three_bin_classifier_mode(raw)
        missing_default_fields = _missing_default_config_fields(raw)
        cfg = AppConfig.model_validate(raw)
        cfg, changed = _repair_config(cfg, path)
        if changed or missing_default_fields or migrated_mode:
            save_config(cfg, path)
        return cfg
    except Exception:
        backup = path.with_suffix(path.suffix + ".broken")
        shutil.copy2(path, backup)
        cfg, _changed = _repair_config(AppConfig(), path)
        save_config(cfg, path)
        return cfg
