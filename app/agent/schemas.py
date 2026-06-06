"""DTOs exposed by the local web agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import AppConfig, ClassMapping


class DeviceState(BaseModel):
    connected: bool = False
    running: bool = False
    message: str = ""


class RuntimeStatus(BaseModel):
    camera: DeviceState = Field(default_factory=DeviceState)
    uart: DeviceState = Field(default_factory=DeviceState)
    model: DeviceState = Field(default_factory=DeviceState)
    fps: float = 0.0
    latency_ms: float = 0.0
    current_source: str = ""
    current_port: str = ""
    usb_cameras: list[dict[str, object]] = Field(default_factory=list)
    serial_ports: list[dict[str, object]] = Field(default_factory=list)


class AuthMeResponse(BaseModel):
    role: Literal["admin", "user"]
    capabilities: list[str] = Field(default_factory=list)
    auth_required: bool = False


class DetectionDTO(BaseModel):
    cls_id: int
    cls_name: str
    confidence: float
    bbox: tuple[int, int, int, int]
    track_id: int | None = None
    timestamp: str
    uart_command: str | None = None
    route_label: str | None = None
    bin_index: int | None = None
    serial_payload: str | None = None
    ack: str | None = None


class ActuationEvidenceDTO(BaseModel):
    history_id: int
    timestamp: str
    detected_class: str
    confidence: float
    route_label: str | None = None
    bin_index: int | None = None
    command: str | None = None
    serial_payload: str | None = None
    uart_sent: bool = False
    ack_status: str | None = None
    rtt_ms: int | None = None


class ActuationTestModeRequest(BaseModel):
    enabled: bool


class ActuationTestModeResponse(BaseModel):
    enabled: bool = False
    uart_connected: bool = False
    warning: str = ""
    evidence: list[ActuationEvidenceDTO] = Field(default_factory=list)


class ModelClassDTO(BaseModel):
    id: int
    name: str


class ModelClassesResponse(BaseModel):
    classes: list[ModelClassDTO]


class CommonWasteItemDTO(BaseModel):
    label: str
    canonical_class: str
    class_id: int | None = None
    aliases: list[str] = Field(default_factory=list)
    command: str
    bin_index: int
    route_label: str
    notes: str = ""


class CommonWasteCatalogResponse(BaseModel):
    items: list[CommonWasteItemDTO]


class DatasetSummaryDTO(BaseModel):
    images: int
    boxes: int
    classes: dict[str, int]
    sources: dict[str, int]
    catalog_total: int
    box_catalog_total: int = 0
    class_catalog_total: int = 0
    trainable_total: int = 0
    needs_review_total: int = 0
    out_of_sync: bool
    needs_sync: bool = False
    missing_meta: int
    queue_dir: str
    catalog_path: str


class BinFullnessDTO(BaseModel):
    bin_index: int
    label: str
    percent: int = Field(0, ge=0, le=100)
    updated_at: str | None = None
    stale: bool = True


class WasteClassCountDTO(BaseModel):
    cls_name: str
    count: int
    bin_index: int | None = None
    route_label: str | None = None


class WellnessInsightDTO(BaseModel):
    kind: str
    title: str
    message: str
    severity: Literal["info", "warning"] = "info"


class UserDashboardResponse(BaseModel):
    generated_at: str
    bins: list[BinFullnessDTO]
    recent_waste: list[WasteClassCountDTO] = Field(default_factory=list)
    insights: list[WellnessInsightDTO] = Field(default_factory=list)
    sample_size: int = 0


class HardwareTestRequest(BaseModel):
    command: Literal["O", "R", "I"]


class CameraSampleRequest(BaseModel):
    cls_name: str
    cls_id: int = 0
    use_latest_detection_box: bool = True


class CaptureSessionStartRequest(BaseModel):
    cls_name: str
    cls_id: int = 0
    target_count: int = Field(24, ge=4, le=100)
    holdout_count: int = Field(6, ge=1, le=30)


class CaptureSessionFrameRequest(BaseModel):
    pose_index: int = Field(0, ge=0, le=1000)
    use_latest_detection_box: bool = True


class CaptureSessionResponse(BaseModel):
    active: bool = False
    session_id: str = ""
    cls_name: str = ""
    cls_id: int = 0
    target_count: int = 24
    holdout_count: int = 6
    accepted_count: int = 0
    training_count: int = 0
    holdout_accepted: int = 0
    rejected_count: int = 0
    last_message: str = ""
    last_image_path: str = ""


class ManualUrlImportRequest(BaseModel):
    urls: list[str]
    cls_name: str
    cls_id: int = 0
    source_page_url: str = ""
    source_license: str = ""
    source_author: str = ""


class HardwareAudioTestRequest(BaseModel):
    track: int = Field(..., ge=1, le=7)


class HardwareMp3TestRequest(BaseModel):
    command: Literal[
        "TF",
        "VOL",
        "PLAY",
        "PLAYVOL",
        "NEXT",
        "ONLINE",
        "STATUS",
        "RESET",
        "MODE_PRIMARY",
        "MODE_REVERSE",
        "MODE_QUERY",
    ]
    value: int | None = None


class ServoAngleTestRequest(BaseModel):
    d6: int = Field(..., ge=0, le=180)
    d7: int = Field(..., ge=0, le=180)
    label: str = ""


class SortAngleTestRequest(BaseModel):
    command: Literal["O", "R", "I"]
    d6: int = Field(..., ge=0, le=180)
    d7: int = Field(..., ge=0, le=180)
    label: str = ""


class HardwareProfileResponse(BaseModel):
    profile_id: str = ""
    profile_name: str = ""
    audio_protocol: str = ""
    baud: int
    protocol: str
    servo: dict[str, object]
    calibration: dict[str, object] = Field(default_factory=dict)
    gd5800: dict[str, object]
    routes: list[dict[str, object]]
    bin_sensors: list[dict[str, object]]
    proximity_sensors: list[dict[str, object]] = Field(default_factory=list)
    current_port: str = ""
    uart_message: str = ""


class HardwareDiagnosticsResponse(BaseModel):
    selected_port: str = ""
    uart_running: bool = False
    uart_connected: bool = False
    uart_message: str = ""
    eligible_ports: list[dict[str, object]] = Field(default_factory=list)
    firmware_profile: str = ""
    firmware_profile_age_s: float | None = None
    last_pong_age_s: float | None = None
    last_ack: dict[str, object] = Field(default_factory=dict)
    last_proximity: dict[str, object] = Field(default_factory=dict)
    last_audio: dict[str, object] = Field(default_factory=dict)
    last_mp3: dict[str, object] = Field(default_factory=dict)
    last_mp3_tx: dict[str, object] = Field(default_factory=dict)
    last_mp3_rx: dict[str, object] = Field(default_factory=dict)
    last_servo: dict[str, object] = Field(default_factory=dict)
    audio_protocol: str = ""
    current_home: dict[str, object] = Field(default_factory=dict)
    current_inorganic: dict[str, object] = Field(default_factory=dict)
    current_vo_co: dict[str, object] = Field(default_factory=dict)
    current_tai_che: dict[str, object] = Field(default_factory=dict)
    last_log: str = ""
    disconnect_reason: str = ""
    warning: str = ""


class HardwareTestResponse(BaseModel):
    ok: bool
    command: Literal["O", "R", "I"]
    payload: str
    port: str = ""
    ack_status: str = ""
    elapsed_ms: int = 0
    message: str = ""


class HardwareAudioTestResponse(BaseModel):
    ok: bool
    track: int = Field(..., ge=1, le=7)
    payload: str
    port: str = ""
    ack_status: str = ""
    elapsed_ms: int = 0
    message: str = ""


class HardwareMp3TestResponse(BaseModel):
    ok: bool
    command: Literal[
        "TF",
        "VOL",
        "PLAY",
        "PLAYVOL",
        "NEXT",
        "ONLINE",
        "STATUS",
        "RESET",
        "MODE_PRIMARY",
        "MODE_REVERSE",
        "MODE_QUERY",
    ]
    value: int | None = None
    payload: str
    port: str = ""
    ack_status: str = ""
    elapsed_ms: int = 0
    message: str = ""


class ServoAngleTestResponse(BaseModel):
    ok: bool
    command: str = "ANGLE"
    route_command: str | None = None
    payload: str
    port: str = ""
    ack_status: str = ""
    elapsed_ms: int = 0
    message: str = ""
    d6: int | None = None
    d7: int | None = None
    label: str = ""


class DatasetItemDTO(BaseModel):
    item_id: str
    image_path: str
    meta_path: str
    source: str
    cls_id: int | None = None
    cls_name: str | None = None
    box_count: int = 0
    width: int | None = None
    height: int | None = None
    split: str | None = None
    original_file: str | None = None
    ts: str | None = None
    updated_at: str
    trusted: bool = True
    reviewed: bool = False


class DatasetItemsResponse(BaseModel):
    rows: list[DatasetItemDTO]
    total: int


class DatasetBoxDTO(BaseModel):
    cls_id: int
    cls_name: str
    conf: float = 1.0
    xyxy: tuple[float, float, float, float]


class DatasetAnnotationResponse(BaseModel):
    item: DatasetItemDTO
    boxes: list[DatasetBoxDTO]


class AnnotationRequest(BaseModel):
    boxes: list[DatasetBoxDTO]


class BulkDatasetRequest(BaseModel):
    action: Literal["delete", "relabel", "quarantine", "mark_trusted", "mark_untrusted"]
    image_paths: list[str]
    cls_name: str | None = None
    cls_id: int | None = None


class ActionResult(BaseModel):
    ok: bool
    message: str = ""
    count: int = 0


class HistoryRowDTO(BaseModel):
    id: int
    track_id: int
    ts: str
    cls_id: int
    cls_name: str
    conf: float
    bbox: tuple[int | None, int | None, int | None, int | None]
    image_path: str | None = None
    annotated_path: str | None = None
    meta_path: str | None = None
    route_label: str | None = None
    bin_index: int | None = None
    uart_command: str | None = None
    ack_status: str | None = None
    rtt_ms: int | None = None


class HistoryResponse(BaseModel):
    rows: list[HistoryRowDTO]
    total: int


class TrainingStatusDTO(BaseModel):
    running: bool = False
    run_name: str = ""
    log_path: str = ""
    results_path: str = ""
    best_model_path: str = ""
    last_model_path: str = ""
    segment_epoch: int | None = None
    segment_epochs: int | None = None
    completed_epoch: int | None = None
    target_epoch: int | None = None
    progress_percent: float = 0.0
    precision: float | None = None
    recall: float | None = None
    map50: float | None = None
    map5095: float | None = None
    message: str = ""


class SettingsResponse(BaseModel):
    config: AppConfig


class MappingsResponse(BaseModel):
    mappings: list[ClassMapping]


class RelabelRequest(BaseModel):
    image_paths: list[str]
    cls_name: str
    cls_id: int


class DeleteRequest(BaseModel):
    image_paths: list[str]


class HealthResponse(BaseModel):
    ok: bool = True
    app: str = "Trash Sorter Pro Agent"
    version: str = "2.0.0"


__all__ = [
    "ActionResult",
    "ActuationEvidenceDTO",
    "ActuationTestModeRequest",
    "ActuationTestModeResponse",
    "AnnotationRequest",
    "AuthMeResponse",
    "BinFullnessDTO",
    "BulkDatasetRequest",
    "CameraSampleRequest",
    "CaptureSessionFrameRequest",
    "CaptureSessionResponse",
    "CaptureSessionStartRequest",
    "CommonWasteCatalogResponse",
    "CommonWasteItemDTO",
    "DatasetAnnotationResponse",
    "DatasetBoxDTO",
    "DatasetItemDTO",
    "DatasetItemsResponse",
    "DatasetSummaryDTO",
    "DeleteRequest",
    "DetectionDTO",
    "HardwareAudioTestRequest",
    "HardwareAudioTestResponse",
    "HardwareDiagnosticsResponse",
    "HardwareMp3TestRequest",
    "HardwareMp3TestResponse",
    "HardwareProfileResponse",
    "HardwareTestRequest",
    "HardwareTestResponse",
    "HealthResponse",
    "HistoryResponse",
    "HistoryRowDTO",
    "ManualUrlImportRequest",
    "MappingsResponse",
    "ModelClassesResponse",
    "RelabelRequest",
    "RuntimeStatus",
    "ServoAngleTestRequest",
    "ServoAngleTestResponse",
    "SettingsResponse",
    "SortAngleTestRequest",
    "TrainingStatusDTO",
    "UserDashboardResponse",
    "WasteClassCountDTO",
    "WellnessInsightDTO",
]
