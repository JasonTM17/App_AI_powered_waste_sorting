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
    three_bin_classifier: DeviceState = Field(default_factory=DeviceState)
    camera_diagnostics: dict[str, object] = Field(default_factory=dict)
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
    account_id: int | None = None
    username: str | None = None
    token_source: str = "dev"
    session_expires_at: str | None = None
    password_default: bool = False


class AuthLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=200)


class AuthLoginResponse(BaseModel):
    token: str
    role: Literal["admin", "user"]
    account_id: int | None = None
    username: str
    capabilities: list[str] = Field(default_factory=list)
    expires_at: str
    password_default: bool = False


class AuthLogoutResponse(BaseModel):
    ok: bool = True
    message: str = "Logged out"


class AuthChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=200)


class CameraStreamTokenResponse(BaseModel):
    token: str
    expires_at: str


class AudioVoiceEventStatusDTO(BaseModel):
    event_key: str
    label: str
    available: bool


class AudioVoicePackStatusResponse(BaseModel):
    gender: Literal["female", "male"]
    available_count: int
    total_count: int
    missing_events: list[str] = Field(default_factory=list)
    events: list[AudioVoiceEventStatusDTO] = Field(default_factory=list)


class AccountDTO(BaseModel):
    id: int
    username: str
    role: Literal["admin", "user"]
    is_active: bool
    password_default: bool = False
    created_at: str = ""
    last_login_at: str | None = None


class AccountsResponse(BaseModel):
    accounts: list[AccountDTO] = Field(default_factory=list)


class RoleCapabilityDTO(BaseModel):
    role: Literal["admin", "user"]
    label: str
    capabilities: list[str] = Field(default_factory=list)
    description: str = ""


class RoleCatalogResponse(BaseModel):
    roles: list[RoleCapabilityDTO] = Field(default_factory=list)


class OperationDeviceDTO(BaseModel):
    id: int
    device_id: str
    device_name: str
    location: str = ""
    owner_username: str = ""
    status: Literal["online", "offline", "warning", "maintenance"] = "offline"
    message: str = ""
    active: bool = True
    created_at: str = ""
    updated_at: str = ""


class OperationDeviceUpsertRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=120)
    device_name: str = Field(..., min_length=1, max_length=160)
    location: str = Field("", max_length=240)
    owner_username: str = Field("", max_length=80)
    status: Literal["online", "offline", "warning", "maintenance"] = "offline"
    message: str = Field("", max_length=400)
    active: bool = True


class OperationDevicesResponse(BaseModel):
    devices: list[OperationDeviceDTO] = Field(default_factory=list)


class BinChildDTO(BaseModel):
    id: int
    bin_id: str
    station_id: str
    command: Literal["O", "R", "I"]
    bin_index: int
    label: str
    fullness_percent: float | None = None
    fill_percent: float = 0.0
    status: str = "unknown"
    active: bool = True
    updated_at: str = ""


class BinStationDTO(BaseModel):
    id: int
    station_id: str
    name: str
    area: str = ""
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    status: str = "candidate"
    coordinate_verified: bool = False
    source: str = ""
    seed_source: str = ""
    assigned_owner_username: str = ""
    owner_username: str = ""
    device_id: str = ""
    note: str = ""
    active: bool = True
    created_at: str = ""
    updated_at: str = ""
    bins: list[BinChildDTO] = Field(default_factory=list)
    alert_counts: dict[str, int] = Field(default_factory=dict)
    alert_total: int = 0
    open_alert_total: int = 0


class BinMapCenterDTO(BaseModel):
    latitude: float
    longitude: float
    zoom: int = 12


class BinMapResponse(BaseModel):
    generated_at: str
    center: BinMapCenterDTO
    stations: list[BinStationDTO] = Field(default_factory=list)
    total: int = 0
    seed_source: str = ""


class BinStationCreateRequest(BaseModel):
    station_id: str = Field("", max_length=120)
    name: str = Field(..., min_length=1, max_length=180)
    area: str = Field("", max_length=160)
    address: str = Field("", max_length=240)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    status: str = Field("candidate", max_length=40)
    coordinate_verified: bool = False
    source: str = Field("admin", max_length=80)
    assigned_owner_username: str = Field("", max_length=80)
    owner_username: str = Field("", max_length=80)
    device_id: str = Field("", max_length=120)
    note: str = Field("", max_length=400)
    active: bool = True


class BinStationPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    area: str | None = Field(default=None, max_length=160)
    address: str | None = Field(default=None, max_length=240)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    status: str | None = Field(default=None, max_length=40)
    coordinate_verified: bool | None = None
    source: str | None = Field(default=None, max_length=80)
    assigned_owner_username: str | None = Field(default=None, max_length=80)
    owner_username: str | None = Field(default=None, max_length=80)
    device_id: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=400)
    active: bool | None = None


class AlertDTO(BaseModel):
    id: int = 0
    alert_id: str
    station_id: str = ""
    bin_id: str = ""
    device_id: str = ""
    severity: Literal["info", "warning", "danger", "success"] = "info"
    title: str
    message: str = ""
    status: Literal["open", "acknowledged", "resolved"] = "open"
    source: str = "manual"
    created_at: str = ""
    updated_at: str = ""
    resolved_at: str = ""
    actor_username: str = ""
    derived: bool = False


class AlertsResponse(BaseModel):
    alerts: list[AlertDTO] = Field(default_factory=list)
    total: int = 0


class AlertPatchRequest(BaseModel):
    status: Literal["open", "acknowledged", "resolved"]


class CollectionScheduleDTO(BaseModel):
    id: int
    schedule_id: str
    station_id: str
    station_name: str
    assigned_owner_username: str = ""
    scheduled_date: str
    window_start: str = ""
    window_end: str = ""
    status: str = "scheduled"
    state: Literal["scheduled", "due_today", "overdue", "upcoming", "completed"] = "scheduled"
    completed_at: str | None = None
    completed_by: str = ""
    note: str = ""
    created_at: str = ""
    updated_at: str = ""


class CollectionSchedulesResponse(BaseModel):
    schedules: list[CollectionScheduleDTO] = Field(default_factory=list)
    total: int = 0


class CollectionCompleteRequest(BaseModel):
    note: str = Field("", max_length=400)


class CollectionCompleteResponse(BaseModel):
    ok: bool = True
    schedule: CollectionScheduleDTO
    already_completed: bool = False
    message: str = "Collection marked complete"


class DeviceIssueCreateRequest(BaseModel):
    station_id: str = Field("", max_length=120)
    bin_id: str = Field("", max_length=120)
    device_id: str = Field("", max_length=120)
    issue_type: Literal[
        "full_bin",
        "sensor_problem",
        "camera_problem",
        "servo_problem",
        "audio_problem",
        "dirty_bin",
        "other",
    ] = "other"
    severity: Literal["info", "warning", "danger"] = "warning"
    description: str = Field(..., min_length=1, max_length=800)


class DeviceIssueDTO(BaseModel):
    id: int
    issue_id: str
    station_id: str = ""
    bin_id: str = ""
    device_id: str = ""
    issue_type: str
    severity: Literal["info", "warning", "danger"] = "warning"
    description: str = ""
    status: Literal["open", "acknowledged", "resolved"] = "open"
    reporter_username: str = ""
    reporter_account_id: int | None = None
    alert_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    resolved_at: str = ""


class DeviceIssueResponse(BaseModel):
    ok: bool = True
    issue: DeviceIssueDTO
    message: str = "Device issue reported"


class OperationsHealthResponse(BaseModel):
    ok: bool = False
    path: str = ""
    station_total: int = 0
    bin_total: int = 0
    schedule_total: int = 0
    seed_source: str = ""


class AccountCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=8, max_length=200)
    role: Literal["admin", "user"]


class AccountPasswordResetRequest(BaseModel):
    password: str = Field(..., min_length=8, max_length=200)


class AccountPatchRequest(BaseModel):
    is_active: bool


class KnowledgeEntryDTO(BaseModel):
    id: str
    title: str
    roles: list[Literal["admin", "user"]] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    text: str
    enabled: bool = True
    updated_at: str = ""
    source: Literal["seed", "local"] = "seed"


class KnowledgeCatalogResponse(BaseModel):
    entries: list[KnowledgeEntryDTO] = Field(default_factory=list)
    total: int = 0
    enabled_total: int = 0
    local_path: str = ""
    status: str = "ok"
    error: str = ""


class KnowledgeEntryUpsertRequest(BaseModel):
    id: str = Field("", max_length=80)
    title: str = Field(..., min_length=1, max_length=140)
    roles: list[Literal["admin", "user"]] = Field(default_factory=lambda: ["admin", "user"])
    keywords: list[str] = Field(default_factory=list, max_length=30)
    text: str = Field(..., min_length=1, max_length=1600)
    enabled: bool = True


class KnowledgeEntryPatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=140)
    roles: list[Literal["admin", "user"]] | None = None
    keywords: list[str] | None = Field(default=None, max_length=30)
    text: str | None = Field(default=None, min_length=1, max_length=1600)
    enabled: bool | None = None


class KnowledgeEvaluateRequest(BaseModel):
    role: Literal["admin", "user"] = "admin"
    question: str = Field(..., min_length=1, max_length=800)


class KnowledgeScoreDTO(BaseModel):
    id: str
    title: str
    score: int = 0


class KnowledgeEvaluateResponse(BaseModel):
    role: Literal["admin", "user"]
    question: str
    snippets: list[KnowledgeEntryDTO] = Field(default_factory=list)
    scores: list[KnowledgeScoreDTO] = Field(default_factory=list)
    payload_chars: int = 0


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
    source: str = "YOLO"


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


class LearnNowClassStatusDTO(BaseModel):
    class_name: str
    class_id: int | None = None
    command: str
    bin_index: int
    route_label: str
    priority: Literal["P0", "P1", "P2", "other"] = "other"
    images: int = 0
    trainable_count: int = 0
    reviewed_count: int = 0
    manual_reviewed_count: int = 0
    reference_count: int = 0
    holdout_count: int = 0
    generated_count: int = 0
    generated_cap: int = 0
    generated_over_cap: bool = False
    source_issue_count: int = 0
    missing_for_reference: int = 0
    missing_for_micro_train: int = 0
    missing_for_strong_train: int = 0
    missing_holdout_for_strong: int = 0
    ready_for_reference: bool = False
    ready_for_micro_train: bool = False
    ready_for_strong_train: bool = False
    recommended_action: Literal["reference_only", "micro_train", "strong_train"] = "reference_only"
    message: str = ""


class LearnNowStatusResponse(BaseModel):
    selected_class: str = ""
    selected: LearnNowClassStatusDTO | None = None
    classes: list[LearnNowClassStatusDTO] = Field(default_factory=list)
    blocked_labels: dict[str, int] = Field(default_factory=dict)
    total_images: int = 0
    total_boxes: int = 0
    queue_dir: str = ""


class LearnNowTrainRequest(BaseModel):
    cls_name: str
    profile: Literal["micro", "strong"] = "micro"


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


class SourceQualityIssueDTO(BaseModel):
    image: str
    reason: str
    score: float | None = None


class SourceQualityClassDTO(BaseModel):
    class_name: str
    priority: Literal["P0", "P1", "P2", "other"] = "other"
    images: int = 0
    trainable_count: int = 0
    reviewed_count: int = 0
    holdout_count: int = 0
    generated_count: int = 0
    augmented_count: int = 0
    generated_cap: int = 0
    generated_over_cap: bool = False
    source_issue_count: int = 0
    missing_for_reference: int = 0
    missing_for_strong_train: int = 0
    missing_holdout_for_strong: int = 0


class SourceQualityResponse(BaseModel):
    queue_dir: str = ""
    total_images: int = 0
    manual_web_images: int = 0
    generated_images: int = 0
    augmented_images: int = 0
    invalid_source_images: int = 0
    duplicate_images: int = 0
    blurry_images: int = 0
    sources: dict[str, int] = Field(default_factory=dict)
    classes: list[SourceQualityClassDTO] = Field(default_factory=list)
    issues: list[SourceQualityIssueDTO] = Field(default_factory=list)


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
    percent: float = 0.0


class WellnessInsightDTO(BaseModel):
    kind: str
    title: str
    message: str
    severity: Literal["info", "warning"] = "info"


class DeviceStatusDTO(BaseModel):
    device_id: str = ""
    device_name: str = ""
    location: str = ""
    owner_username: str = ""
    online: bool = False
    status: Literal["online", "offline", "warning"] = "offline"
    message: str = ""
    last_active_at: str | None = None
    bins: list[BinFullnessDTO] = Field(default_factory=list)


class EcoScoreDTO(BaseModel):
    score: int = Field(0, ge=0, le=100)
    label: str = ""
    recyclable_rate: float = 0.0
    inorganic_rate: float = 0.0
    organic_rate: float = 0.0
    consistency_score: float = 0.0


class UserHistoryItemDTO(BaseModel):
    id: int
    ts: str
    cls_name: str
    confidence: float
    route_label: str | None = None
    bin_index: int | None = None
    category: Literal["organic", "inorganic", "recyclable"] = "inorganic"
    ack_status: str | None = None
    device_id: str | None = None
    image_available: bool = False


class UserHistoryResponse(BaseModel):
    rows: list[UserHistoryItemDTO] = Field(default_factory=list)
    total: int = 0


class UserDashboardResponse(BaseModel):
    generated_at: str
    bins: list[BinFullnessDTO]
    recent_waste: list[WasteClassCountDTO] = Field(default_factory=list)
    insights: list[WellnessInsightDTO] = Field(default_factory=list)
    sample_size: int = 0


class UserRouteTotalDTO(BaseModel):
    command: Literal["O", "R", "I"]
    route_label: str
    bin_index: int
    count: int = 0
    percent: float = 0.0


class UserDailyWasteDTO(BaseModel):
    date: str
    total: int = 0
    organic: int = 0
    inorganic: int = 0
    recyclable: int = 0


class UserMonthlyWasteDTO(BaseModel):
    month: str
    total: int = 0
    organic: int = 0
    inorganic: int = 0
    recyclable: int = 0


class UserPeriodComparisonDTO(BaseModel):
    previous_total: int = 0
    delta: int = 0
    delta_percent: float = 0.0


class UserYesterdaySummaryDTO(BaseModel):
    date: str
    total: int = 0
    top_classes: list[WasteClassCountDTO] = Field(default_factory=list)
    route_totals: list[UserRouteTotalDTO] = Field(default_factory=list)


class UserAnalyticsResponse(BaseModel):
    generated_at: str
    range_days: Literal[7, 30, 90, 180]
    total: int = 0
    today_total: int = 0
    seven_day_total: int = 0
    thirty_day_total: int = 0
    average_confidence: float = 0.0
    eco_score: EcoScoreDTO = Field(default_factory=EcoScoreDTO)
    device_status: DeviceStatusDTO = Field(default_factory=DeviceStatusDTO)
    advice: list[WellnessInsightDTO] = Field(default_factory=list)
    recent_classifications: list[UserHistoryItemDTO] = Field(default_factory=list)
    comparison: UserPeriodComparisonDTO = Field(default_factory=UserPeriodComparisonDTO)
    bins: list[BinFullnessDTO]
    route_totals: list[UserRouteTotalDTO] = Field(default_factory=list)
    top_classes: list[WasteClassCountDTO] = Field(default_factory=list)
    daily: list[UserDailyWasteDTO] = Field(default_factory=list)
    monthly: list[UserMonthlyWasteDTO] = Field(default_factory=list)
    yesterday: UserYesterdaySummaryDTO
    insights: list[WellnessInsightDTO] = Field(default_factory=list)
    advisor_available: bool = False
    advisor_model: str = ""


class UserDeviceResponse(BaseModel):
    generated_at: str
    device_status: DeviceStatusDTO = Field(default_factory=DeviceStatusDTO)
    bins: list[BinFullnessDTO] = Field(default_factory=list)
    recent_activity: list[UserHistoryItemDTO] = Field(default_factory=list)
    owner_username: str = ""


class UserReportCardDTO(BaseModel):
    title: str
    value: str
    detail: str = ""
    tone: Literal["neutral", "success", "warning", "danger"] = "neutral"


class UserReportResponse(BaseModel):
    generated_at: str
    range_days: Literal[7, 30, 90, 180]
    analytics: UserAnalyticsResponse
    summary_cards: list[UserReportCardDTO] = Field(default_factory=list)
    export_url: str = ""
    csv_safe_fields: list[str] = Field(default_factory=list)


class UserNotificationDTO(BaseModel):
    id: str
    title: str
    message: str
    severity: Literal["info", "success", "warning", "danger"] = "info"
    created_at: str
    route: str = "/user/dashboard"
    action_label: str = "Xem"


class UserChallengeDTO(BaseModel):
    id: str
    title: str
    description: str
    progress: float = 0.0
    target: float = 1.0
    unit: str = "lượt"
    completed: bool = False
    reward_label: str = ""


class UserLeaderboardRowDTO(BaseModel):
    rank: int
    label: str
    score: int
    detail: str = ""
    current_user: bool = False


class UserCommunityCardDTO(BaseModel):
    id: str
    title: str
    message: str
    metric: str = ""
    share_text: str = ""
    tone: Literal["neutral", "success", "warning"] = "neutral"


class UserExperienceResponse(BaseModel):
    generated_at: str
    range_days: Literal[7, 30, 90, 180]
    notifications: list[UserNotificationDTO] = Field(default_factory=list)
    challenges: list[UserChallengeDTO] = Field(default_factory=list)
    leaderboard: list[UserLeaderboardRowDTO] = Field(default_factory=list)
    community_cards: list[UserCommunityCardDTO] = Field(default_factory=list)
    quick_actions: list[dict[str, str]] = Field(default_factory=list)


class UserAdvisorRequest(BaseModel):
    range_days: Literal[7, 30, 90, 180] = 30
    question: str = Field("", max_length=400)


class UserAdvisorResponse(BaseModel):
    generated_at: str
    available: bool = False
    provider: str = "local"
    model: str = ""
    profile: str = ""
    range_days: Literal[7, 30, 90, 180] = 30
    message: str
    local_insights: list[WellnessInsightDTO] = Field(default_factory=list)
    knowledge_used: list[str] = Field(default_factory=list)
    safety_notice: str = ""
    quota_limit: int | None = None
    quota_used: int | None = None
    quota_remaining: int | None = None
    quota_reset_at: str = ""
    quota_exceeded: bool = False


class AiChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=800)


class AiChatResponse(BaseModel):
    generated_at: str
    available: bool = False
    provider: str = "deepseek"
    model: str = ""
    answer_source: Literal["local", "deepseek", "hybrid"] = "local"
    latency_ms: float = 0.0
    role: Literal["admin", "user"]
    profile: str = ""
    message: str
    quick_prompts: list[str] = Field(default_factory=list)
    knowledge_used: list[str] = Field(default_factory=list)
    safety_notice: str = ""
    quota_limit: int | None = None
    quota_used: int | None = None
    quota_remaining: int | None = None
    quota_reset_at: str = ""
    quota_exceeded: bool = False


class HardwareTestRequest(BaseModel):
    command: Literal["O", "R", "I"]


class CameraSampleRequest(BaseModel):
    cls_name: str
    cls_id: int = 0
    use_latest_detection_box: bool = True


class HardNegativeCaptureRequest(BaseModel):
    reason: Literal[
        "empty_tray",
        "hand_only",
        "background_clutter",
        "two_objects",
        "outside_roi",
        "cloth_non_waste",
        "wire_or_fixture",
        "blur_or_motion",
    ]


class UnknownLearnRequest(BaseModel):
    manual_hint: str = ""
    approved_cls_name: str = ""
    cls_id: int = -1


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
    source_type: Literal["licensed_url", "open_images", "wikimedia", "roboflow", "generated", "other"] = (
        "licensed_url"
    )
    generated: bool = False


class WebSourceDiscoveryRequest(BaseModel):
    cls_name: str
    query: str = ""
    limit: int = Field(10, ge=1, le=10)


class HardwareAudioTestRequest(BaseModel):
    track: int = Field(..., ge=1, le=8)


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
    track: int = Field(..., ge=1, le=8)
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
    trust_state: str = ""
    trust_reasons: list[str] = Field(default_factory=list)
    review_decision: str = ""
    review_reason: str = ""
    reviewed_by: str = ""
    bbox_reviewed: bool = False
    training_excluded: bool = False
    quarantined: bool = False
    quarantine_reason: str = ""


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


class VisionLabelSuggestionDTO(BaseModel):
    label: str
    canonical_class: str
    class_id: int
    confidence: float
    command: str
    bin_index: int
    route_label: str
    source: str
    reason: str = ""


class UnknownLearnResponse(BaseModel):
    ok: bool = True
    message: str = ""
    provider: str = ""
    provider_available: bool = False
    hardware_blocked: bool = True
    item: DatasetItemDTO | None = None
    boxes: list[DatasetBoxDTO] = Field(default_factory=list)
    suggestions: list[VisionLabelSuggestionDTO] = Field(default_factory=list)
    learn_status: LearnNowClassStatusDTO | None = None


class WebSourceCandidateDTO(BaseModel):
    title: str
    image_url: str
    source_page_url: str
    source_type: str
    canonical_class: str
    license: str = ""
    author: str = ""
    thumbnail_url: str = ""
    import_ready: bool = False
    reason: str = ""


class WebSourceDiscoveryResponse(BaseModel):
    available: bool = False
    message: str = ""
    candidates: list[WebSourceCandidateDTO] = Field(default_factory=list)


class AnnotationRequest(BaseModel):
    boxes: list[DatasetBoxDTO]


class DatasetReviewRequestDTO(BaseModel):
    action: Literal[
        "approve",
        "relabel",
        "bbox_approved",
        "needs_annotation",
        "hard_negative",
        "holdout",
        "quarantine",
        "exclude",
    ]
    cls_name: str | None = None
    cls_id: int | None = None
    reason: str = ""
    actor: str | None = None
    boxes: list[DatasetBoxDTO] = Field(default_factory=list)


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
    owner_account_id: int | None = None
    owner_username: str | None = None
    device_id: str | None = None


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
    version: str = "1.0.0"


__all__ = [
    "AccountCreateRequest",
    "AccountDTO",
    "AccountPasswordResetRequest",
    "AccountPatchRequest",
    "AccountsResponse",
    "ActionResult",
    "ActuationEvidenceDTO",
    "ActuationTestModeRequest",
    "ActuationTestModeResponse",
    "AiChatRequest",
    "AiChatResponse",
    "AlertDTO",
    "AlertPatchRequest",
    "AlertsResponse",
    "AnnotationRequest",
    "AudioVoiceEventStatusDTO",
    "AudioVoicePackStatusResponse",
    "AuthChangePasswordRequest",
    "AuthLoginRequest",
    "AuthLoginResponse",
    "AuthLogoutResponse",
    "AuthMeResponse",
    "BinChildDTO",
    "BinFullnessDTO",
    "BinMapCenterDTO",
    "BinMapResponse",
    "BinStationCreateRequest",
    "BinStationDTO",
    "BinStationPatchRequest",
    "BulkDatasetRequest",
    "CameraSampleRequest",
    "CameraStreamTokenResponse",
    "CaptureSessionFrameRequest",
    "CaptureSessionResponse",
    "CaptureSessionStartRequest",
    "CollectionCompleteRequest",
    "CollectionCompleteResponse",
    "CollectionScheduleDTO",
    "CollectionSchedulesResponse",
    "CommonWasteCatalogResponse",
    "CommonWasteItemDTO",
    "DatasetAnnotationResponse",
    "DatasetBoxDTO",
    "DatasetItemDTO",
    "DatasetItemsResponse",
    "DatasetReviewRequestDTO",
    "DatasetSummaryDTO",
    "DeleteRequest",
    "DetectionDTO",
    "DeviceIssueCreateRequest",
    "DeviceIssueDTO",
    "DeviceIssueResponse",
    "DeviceStatusDTO",
    "EcoScoreDTO",
    "HardNegativeCaptureRequest",
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
    "LearnNowClassStatusDTO",
    "LearnNowStatusResponse",
    "LearnNowTrainRequest",
    "ManualUrlImportRequest",
    "MappingsResponse",
    "ModelClassesResponse",
    "OperationDeviceDTO",
    "OperationDeviceUpsertRequest",
    "OperationDevicesResponse",
    "OperationsHealthResponse",
    "RelabelRequest",
    "RoleCapabilityDTO",
    "RoleCatalogResponse",
    "RuntimeStatus",
    "ServoAngleTestRequest",
    "ServoAngleTestResponse",
    "SettingsResponse",
    "SortAngleTestRequest",
    "SourceQualityResponse",
    "TrainingStatusDTO",
    "UserAdvisorRequest",
    "UserAdvisorResponse",
    "UserAnalyticsResponse",
    "UserChallengeDTO",
    "UserCommunityCardDTO",
    "UserDailyWasteDTO",
    "UserDashboardResponse",
    "UserDeviceResponse",
    "UserExperienceResponse",
    "UserHistoryItemDTO",
    "UserHistoryResponse",
    "UserLeaderboardRowDTO",
    "UserMonthlyWasteDTO",
    "UserNotificationDTO",
    "UserPeriodComparisonDTO",
    "UserReportCardDTO",
    "UserReportResponse",
    "UserRouteTotalDTO",
    "UserYesterdaySummaryDTO",
    "WasteClassCountDTO",
    "WellnessInsightDTO",
]
