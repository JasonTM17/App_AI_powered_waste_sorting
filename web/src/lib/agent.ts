export type DeviceState = {
  connected: boolean;
  running: boolean;
  message: string;
};

export type RuntimeStatus = {
  camera: DeviceState;
  uart: DeviceState;
  model: DeviceState;
  three_bin_classifier: DeviceState;
  camera_diagnostics?: Record<string, unknown>;
  fps: number;
  latency_ms: number;
  current_source: string;
  current_port: string;
  usb_cameras: Array<Record<string, unknown>>;
  serial_ports: Array<Record<string, unknown>>;
};

export type ClassMapping = {
  class_name: string;
  command: string;
  bin_index: number;
  enabled: boolean;
};

export type ModelClass = {
  id: number;
  name: string;
};

export type CommonWasteItem = {
  label: string;
  canonical_class: string;
  class_id?: number | null;
  aliases: string[];
  command: string;
  bin_index: number;
  route_label: string;
  notes: string;
};

export type LearnNowClassStatus = {
  class_name: string;
  class_id?: number | null;
  command: string;
  bin_index: number;
  route_label: string;
  priority: "P0" | "P1" | "P2" | "other";
  images: number;
  trainable_count: number;
  reviewed_count: number;
  manual_reviewed_count: number;
  reference_count: number;
  holdout_count: number;
  generated_count: number;
  augmented_count: number;
  generated_cap: number;
  generated_over_cap: boolean;
  source_issue_count: number;
  missing_for_reference: number;
  missing_for_micro_train: number;
  missing_for_strong_train: number;
  missing_holdout_for_strong: number;
  ready_for_reference: boolean;
  ready_for_micro_train: boolean;
  ready_for_strong_train: boolean;
  recommended_action: "reference_only" | "micro_train" | "strong_train";
  message: string;
};

export type LearnNowStatus = {
  selected_class: string;
  selected?: LearnNowClassStatus | null;
  classes: LearnNowClassStatus[];
  blocked_labels: Record<string, number>;
  total_images: number;
  total_boxes: number;
  queue_dir: string;
};

export type AppConfig = {
  camera: {
    source: string;
    width: number;
    height: number;
    mirror: boolean;
    rotation: 0 | 90 | 180 | 270;
  };
  model: {
    path: string;
    device: "auto" | "cpu" | "cuda";
    conf_threshold: number;
    iou_threshold: number;
    input_size: number;
    half_precision: boolean;
  };
  uart: {
    port: string;
    baud: number;
    auto_reconnect: boolean;
    ack_timeout_ms: number;
    protocol: "plain_group" | "sort_line";
  };
  device: {
    device_id: string;
    device_name: string;
    location: string;
    owner_username: string;
  };
  mappings: ClassMapping[];
  roi: {
    enabled: boolean;
    x: number;
    y: number;
    width: number;
    height: number;
  };
  dispatch_guard: {
    min_sort_interval_seconds: number;
    busy_settle_seconds: number;
    min_stable_frames: number;
    empty_rearm_seconds: number;
    empty_rearm_frames: number;
    require_roi_for_dispatch: boolean;
    max_classes_per_dispatch: number;
    multi_class_warning_cooldown_seconds: number;
    multi_class_warning_text: string;
    multi_class_warning_audio_track: number;
  };
  manual_reference_recognition: {
    enabled: boolean;
    min_similarity: number;
    min_consensus_similarity: number;
    min_margin: number;
    top_k: number;
    min_votes: number;
    max_references_per_class: number;
    cache_refresh_seconds: number;
    query_cache_seconds: number;
  };
  three_bin_classifier: {
    enabled: boolean;
    model_path: string;
    min_confidence: number;
    min_margin: number;
    unknown_only: boolean;
    min_crop_area_ratio: number;
    input_size: number;
  };
  capture: {
    mode: "off" | "manual" | "auto_low_conf";
    low_conf_threshold: number;
    output_dir: string;
  };
  speaker: {
    enabled: boolean;
    output_mode: "hardware" | "computer_speaker";
    cooldown_seconds: number;
  };
  theme: "dark" | "light";
  language: "vi" | "en";
  minimize_to_tray: boolean;
  autostart: boolean;
};

export type Detection = {
  cls_id: number;
  cls_name: string;
  confidence: number;
  bbox: [number, number, number, number];
  track_id?: number | null;
  timestamp: string;
  uart_command?: string | null;
  route_label?: string | null;
  bin_index?: number | null;
  serial_payload?: string | null;
  ack?: string | null;
  source: string;
};

export type HardwareProfile = {
  profile_id: string;
  profile_name: string;
  audio_protocol?: string;
  baud: number;
  protocol: string;
  servo: Record<string, unknown>;
  calibration?: Record<string, unknown>;
  gd5800: Record<string, unknown>;
  routes: Array<Record<string, unknown>>;
  bin_sensors: Array<Record<string, unknown>>;
  proximity_sensors: Array<Record<string, unknown>>;
  current_port: string;
  uart_message: string;
};

export type HardwareDiagnostics = {
  selected_port: string;
  uart_running: boolean;
  uart_connected: boolean;
  uart_message: string;
  eligible_ports: Array<Record<string, unknown>>;
  firmware_profile: string;
  firmware_profile_age_s?: number | null;
  last_pong_age_s?: number | null;
  last_ack: Record<string, unknown>;
  last_proximity: Record<string, unknown>;
  last_audio: Record<string, unknown>;
  last_mp3: Record<string, unknown>;
  last_mp3_tx: Record<string, unknown>;
  last_mp3_rx: Record<string, unknown>;
  last_servo: Record<string, unknown>;
  audio_protocol: string;
  current_home: Record<string, unknown>;
  current_inorganic: Record<string, unknown>;
  current_vo_co: Record<string, unknown>;
  current_tai_che: Record<string, unknown>;
  last_log: string;
  disconnect_reason: string;
  warning: string;
};

export type HardwareTestResponse = {
  ok: boolean;
  command?: string;
  route_command?: string | null;
  track?: number | null;
  value?: number | null;
  payload: string;
  port: string;
  ack_status: string;
  elapsed_ms: number;
  message: string;
  d6?: number | null;
  d7?: number | null;
  label?: string;
};

export type ActuationEvidence = {
  history_id: number;
  timestamp: string;
  detected_class: string;
  confidence: number;
  route_label?: string | null;
  bin_index?: number | null;
  command?: string | null;
  serial_payload?: string | null;
  uart_sent: boolean;
  ack_status?: string | null;
  rtt_ms?: number | null;
};

export type ActuationTestMode = {
  enabled: boolean;
  uart_connected: boolean;
  warning: string;
  evidence: ActuationEvidence[];
};

export type DatasetSummary = {
  images: number;
  boxes: number;
  classes: Record<string, number>;
  sources: Record<string, number>;
  catalog_total: number;
  box_catalog_total: number;
  class_catalog_total: number;
  trainable_total: number;
  needs_review_total: number;
  out_of_sync: boolean;
  needs_sync: boolean;
  missing_meta: number;
  queue_dir: string;
  catalog_path: string;
};

export type SourceQualityClass = {
  class_name: string;
  priority: "P0" | "P1" | "P2" | "other";
  images: number;
  trainable_count: number;
  reviewed_count: number;
  holdout_count: number;
  generated_count: number;
  augmented_count: number;
  generated_cap: number;
  generated_over_cap: boolean;
  source_issue_count: number;
  missing_for_reference: number;
  missing_for_strong_train: number;
  missing_holdout_for_strong: number;
};

export type SourceQuality = {
  queue_dir: string;
  total_images: number;
  manual_web_images: number;
  generated_images: number;
  augmented_images: number;
  invalid_source_images: number;
  duplicate_images: number;
  blurry_images: number;
  sources: Record<string, number>;
  classes: SourceQualityClass[];
  issues: Array<{ image: string; reason: string; score?: number | null }>;
};

export type DatasetItem = {
  item_id: string;
  image_path: string;
  meta_path: string;
  source: string;
  cls_id?: number | null;
  cls_name?: string | null;
  box_count: number;
  width?: number | null;
  height?: number | null;
  split?: string | null;
  original_file?: string | null;
  ts?: string | null;
  updated_at: string;
  trusted: boolean;
  reviewed: boolean;
};

export type DatasetBox = {
  cls_id: number;
  cls_name: string;
  conf: number;
  xyxy: [number, number, number, number];
};

export type DatasetAnnotationResponse = {
  item: DatasetItem;
  boxes: DatasetBox[];
};

export type VisionLabelSuggestion = {
  label: string;
  canonical_class: string;
  class_id: number;
  confidence: number;
  command: string;
  bin_index: number;
  route_label: string;
  source: string;
  reason: string;
};

export type UnknownLearnResponse = {
  ok: boolean;
  message: string;
  provider: string;
  provider_available: boolean;
  hardware_blocked: boolean;
  item?: DatasetItem | null;
  boxes: DatasetBox[];
  suggestions: VisionLabelSuggestion[];
  learn_status?: LearnNowClassStatus | null;
};

export type WebSourceCandidate = {
  title: string;
  image_url: string;
  source_page_url: string;
  source_type: string;
  canonical_class: string;
  license: string;
  author: string;
  thumbnail_url: string;
  import_ready: boolean;
  reason: string;
};

export type WebSourceDiscoveryResponse = {
  available: boolean;
  message: string;
  candidates: WebSourceCandidate[];
};

export type DatasetItemsResponse = {
  rows: DatasetItem[];
  total: number;
};

export type CaptureSession = {
  active: boolean;
  session_id: string;
  cls_name: string;
  cls_id: number;
  target_count: number;
  holdout_count: number;
  accepted_count: number;
  training_count: number;
  holdout_accepted: number;
  rejected_count: number;
  last_message: string;
  last_image_path: string;
};

export type HistoryRow = {
  id: number;
  track_id: number;
  ts: string;
  cls_id: number;
  cls_name: string;
  conf: number;
  bbox: [number | null, number | null, number | null, number | null];
  image_path?: string | null;
  annotated_path?: string | null;
  meta_path?: string | null;
  route_label?: string | null;
  bin_index?: number | null;
  uart_command?: string | null;
  ack_status?: string | null;
  rtt_ms?: number | null;
  owner_account_id?: number | null;
  owner_username?: string | null;
  device_id?: string | null;
};

export type TrainingStatus = {
  running: boolean;
  run_name: string;
  log_path: string;
  results_path: string;
  best_model_path: string;
  last_model_path: string;
  segment_epoch?: number | null;
  segment_epochs?: number | null;
  completed_epoch?: number | null;
  target_epoch?: number | null;
  progress_percent: number;
  precision?: number | null;
  recall?: number | null;
  map50?: number | null;
  map5095?: number | null;
  message: string;
};

export type AgentSnapshot = {
  status?: RuntimeStatus;
  detections?: Detection[];
};

export type AuthRole = "admin" | "user";

export type AuthMe = {
  role: AuthRole;
  capabilities: string[];
  auth_required: boolean;
  account_id?: number | null;
  username?: string | null;
  token_source: "session" | "env" | "dev" | string;
  session_expires_at?: string | null;
  password_default: boolean;
};

export type AuthLoginResponse = {
  token: string;
  role: AuthRole;
  account_id?: number | null;
  username: string;
  capabilities: string[];
  expires_at: string;
  password_default: boolean;
};

export type AccountDTO = {
  id: number;
  username: string;
  role: AuthRole;
  is_active: boolean;
  password_default: boolean;
  created_at: string;
  last_login_at?: string | null;
};

export type AccountsResponse = {
  accounts: AccountDTO[];
};

export type RoleCapability = {
  id: string;
  label: string;
  description: string;
};

export type RoleDefinition = {
  role: AuthRole;
  label: string;
  capabilities: RoleCapability[];
};

export type RoleCatalogResponse = {
  roles: RoleDefinition[];
};

export type OperationDevice = {
  id: number;
  device_id: string;
  device_name: string;
  location: string;
  owner_username: string;
  status: "online" | "offline" | "warning" | string;
  message: string;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type OperationDevicesResponse = {
  devices: OperationDevice[];
  total: number;
};

export type OperationDeviceUpsertPayload = {
  device_id: string;
  device_name?: string;
  location?: string;
  owner_username?: string;
  status?: string;
  message?: string;
  active?: boolean;
};

export type OperationBin = {
  id: number;
  bin_id: string;
  station_id: string;
  command: "O" | "R" | "I" | string;
  bin_index: number;
  label: string;
  fill_percent: number;
  status: "normal" | "warning" | "full" | "offline" | string;
  active: boolean;
  updated_at: string;
};

export type BinStation = {
  id: number;
  station_id: string;
  name: string;
  area: string;
  address: string;
  latitude?: number | null;
  longitude?: number | null;
  coordinate_verified: boolean;
  status: "candidate" | "active" | "inactive" | "maintenance" | string;
  active: boolean;
  owner_username: string;
  device_id: string;
  note: string;
  seed_source: string;
  alert_total: number;
  open_alert_total: number;
  bins: OperationBin[];
  created_at: string;
  updated_at: string;
};

export type BinMapResponse = {
  generated_at: string;
  center: {
    latitude: number;
    longitude: number;
    zoom: number;
  };
  stations: BinStation[];
  total: number;
};

export type BinStationCreatePayload = {
  station_id?: string;
  name: string;
  area?: string;
  address?: string;
  latitude?: number | null;
  longitude?: number | null;
  coordinate_verified?: boolean;
  status?: string;
  active?: boolean;
  owner_username?: string;
  device_id?: string;
  note?: string;
};

export type BinStationPatchPayload = Partial<Omit<BinStationCreatePayload, "station_id">>;

export type OperationAlert = {
  id: number;
  alert_id: string;
  station_id: string;
  bin_id: string;
  device_id: string;
  severity: "info" | "success" | "warning" | "danger" | string;
  title: string;
  message: string;
  status: "open" | "acknowledged" | "resolved" | string;
  source: string;
  created_at: string;
  updated_at: string;
  resolved_at: string;
  actor_username: string;
  derived: boolean;
};

export type AlertsResponse = {
  alerts: OperationAlert[];
  total: number;
};

export type CollectionSchedule = {
  id: number;
  schedule_id: string;
  station_id: string;
  station_name: string;
  assigned_owner_username: string;
  scheduled_date: string;
  window_start: string;
  window_end: string;
  status: string;
  state: "scheduled" | "due_today" | "overdue" | "upcoming" | "completed";
  completed_at?: string | null;
  completed_by: string;
  note: string;
  created_at: string;
  updated_at: string;
};

export type CollectionSchedulesResponse = {
  schedules: CollectionSchedule[];
  total: number;
};

export type CollectionCompleteResponse = {
  ok: boolean;
  schedule: CollectionSchedule;
  already_completed: boolean;
  message: string;
};

export type DeviceIssue = {
  id: number;
  issue_id: string;
  station_id: string;
  bin_id: string;
  device_id: string;
  issue_type: string;
  severity: "info" | "warning" | "danger" | string;
  description: string;
  status: "open" | "acknowledged" | "resolved" | string;
  reporter_username: string;
  reporter_account_id?: number | null;
  alert_id: string;
  created_at: string;
  updated_at: string;
  resolved_at: string;
};

export type DeviceIssueResponse = {
  issue: DeviceIssue;
  alert: OperationAlert;
  message: string;
};

export type DeviceIssueCreatePayload = {
  station_id?: string;
  bin_id?: string;
  device_id?: string;
  issue_type: string;
  severity: "info" | "warning" | "danger";
  description: string;
};

export type OperationsHealthResponse = {
  ok: boolean;
  path: string;
  station_total: number;
  bin_total: number;
  schedule_total: number;
  seed_source: string;
};

export type BinFullness = {
  bin_index: number;
  label: string;
  percent: number;
  updated_at?: string | null;
  stale: boolean;
};

export type WasteClassCount = {
  cls_name: string;
  count: number;
  bin_index?: number | null;
  route_label?: string | null;
  percent: number;
};

export type WellnessInsight = {
  kind: string;
  title: string;
  message: string;
  severity: "info" | "warning";
};

export type UserDashboard = {
  generated_at: string;
  bins: BinFullness[];
  recent_waste: WasteClassCount[];
  insights: WellnessInsight[];
  sample_size: number;
};

export type AnalyticsRangeDays = 7 | 30 | 90 | 180;

export type UserRouteTotal = {
  command: "O" | "R" | "I";
  route_label: string;
  bin_index: number;
  count: number;
  percent: number;
};

export type UserDailyWaste = {
  date: string;
  total: number;
  organic: number;
  inorganic: number;
  recyclable: number;
};

export type UserMonthlyWaste = {
  month: string;
  total: number;
  organic: number;
  inorganic: number;
  recyclable: number;
};

export type UserPeriodComparison = {
  previous_total: number;
  delta: number;
  delta_percent: number;
};

export type UserYesterdaySummary = {
  date: string;
  total: number;
  top_classes: WasteClassCount[];
  route_totals: UserRouteTotal[];
};

export type DeviceStatus = {
  device_id: string;
  device_name: string;
  location: string;
  owner_username: string;
  online: boolean;
  status: "online" | "offline" | "warning";
  message: string;
  last_active_at?: string | null;
  bins: BinFullness[];
};

export type EcoScore = {
  score: number;
  label: string;
  recyclable_rate: number;
  inorganic_rate: number;
  organic_rate: number;
  consistency_score: number;
};

export type UserHistoryItem = {
  id: number;
  ts: string;
  cls_name: string;
  confidence: number;
  route_label?: string | null;
  bin_index?: number | null;
  category: "organic" | "inorganic" | "recyclable";
  ack_status?: string | null;
  device_id?: string | null;
  image_available: boolean;
};

export type UserHistoryResponse = {
  rows: UserHistoryItem[];
  total: number;
};

export type UserAnalytics = {
  generated_at: string;
  range_days: AnalyticsRangeDays;
  total: number;
  today_total: number;
  seven_day_total: number;
  thirty_day_total: number;
  average_confidence: number;
  eco_score: EcoScore;
  device_status: DeviceStatus;
  advice: WellnessInsight[];
  recent_classifications: UserHistoryItem[];
  comparison: UserPeriodComparison;
  bins: BinFullness[];
  route_totals: UserRouteTotal[];
  top_classes: WasteClassCount[];
  daily: UserDailyWaste[];
  monthly: UserMonthlyWaste[];
  yesterday: UserYesterdaySummary;
  insights: WellnessInsight[];
  advisor_available: boolean;
  advisor_model: string;
};

export type UserDevice = {
  generated_at: string;
  device_status: DeviceStatus;
  bins: BinFullness[];
  recent_activity: UserHistoryItem[];
  owner_username: string;
};

export type UserReportCard = {
  title: string;
  value: string;
  detail: string;
  tone: "neutral" | "success" | "warning" | "danger";
};

export type UserReport = {
  generated_at: string;
  range_days: AnalyticsRangeDays;
  analytics: UserAnalytics;
  summary_cards: UserReportCard[];
  export_url: string;
  csv_safe_fields: string[];
};

export type UserNotification = {
  id: string;
  title: string;
  message: string;
  severity: "info" | "success" | "warning" | "danger";
  created_at: string;
  route: string;
  action_label: string;
};

export type UserChallenge = {
  id: string;
  title: string;
  description: string;
  progress: number;
  target: number;
  unit: string;
  completed: boolean;
  reward_label: string;
};

export type UserLeaderboardRow = {
  rank: number;
  label: string;
  score: number;
  detail: string;
  current_user: boolean;
};

export type UserCommunityCard = {
  id: string;
  title: string;
  message: string;
  metric: string;
  share_text: string;
  tone: "neutral" | "success" | "warning";
};

export type UserExperience = {
  generated_at: string;
  range_days: AnalyticsRangeDays;
  notifications: UserNotification[];
  challenges: UserChallenge[];
  leaderboard: UserLeaderboardRow[];
  community_cards: UserCommunityCard[];
  quick_actions: Array<{ label: string; route: string }>;
};

export type UserAdvisorResponse = {
  generated_at: string;
  available: boolean;
  provider: string;
  model: string;
  profile: string;
  range_days: AnalyticsRangeDays;
  message: string;
  local_insights: WellnessInsight[];
  knowledge_used: string[];
  safety_notice: string;
  quota_limit?: number | null;
  quota_used?: number | null;
  quota_remaining?: number | null;
  quota_reset_at?: string;
  quota_exceeded?: boolean;
};

export type AiChatResponse = {
  generated_at: string;
  available: boolean;
  provider: string;
  model: string;
  role: AuthRole;
  profile: string;
  message: string;
  quick_prompts: string[];
  knowledge_used: string[];
  safety_notice: string;
  quota_limit?: number | null;
  quota_used?: number | null;
  quota_remaining?: number | null;
  quota_reset_at?: string;
  quota_exceeded?: boolean;
};

export type KnowledgeEntry = {
  id: string;
  title: string;
  roles: AuthRole[];
  keywords: string[];
  text: string;
  enabled: boolean;
  updated_at: string;
  source: "seed" | "local";
};

export type KnowledgeCatalogResponse = {
  entries: KnowledgeEntry[];
  total: number;
  enabled_total: number;
  local_path: string;
  status: string;
  error: string;
};

export type KnowledgeScore = {
  id: string;
  title: string;
  score: number;
};

export type KnowledgeEvaluateResponse = {
  role: AuthRole;
  question: string;
  snippets: KnowledgeEntry[];
  scores: KnowledgeScore[];
  payload_chars: number;
};

export const AGENT_URL =
  process.env.NEXT_PUBLIC_AGENT_URL?.replace(/\/$/, "") || "http://localhost:8765";

export const DEFAULT_AGENT_TOKEN = process.env.NEXT_PUBLIC_AGENT_TOKEN || "";
const AGENT_FETCH_TIMEOUT_MS = 20000;

export class AgentApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "AgentApiError";
    this.status = status;
  }
}

export function streamUrl(token = DEFAULT_AGENT_TOKEN) {
  const url = new URL(`${AGENT_URL}/api/camera/stream`);
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

export function websocketUrl(token = DEFAULT_AGENT_TOKEN) {
  const url = new URL(`${AGENT_URL}/ws/live`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

export function datasetImageUrl(itemId: string, token = DEFAULT_AGENT_TOKEN) {
  const url = new URL(`${AGENT_URL}/api/dataset/items/${encodeURIComponent(itemId)}/image`);
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

export function historyImageUrl(
  rowId: number,
  kind: "annotated" | "raw" = "annotated",
  token = DEFAULT_AGENT_TOKEN
) {
  const url = new URL(`${AGENT_URL}/api/history/${encodeURIComponent(String(rowId))}/image`);
  url.searchParams.set("kind", kind);
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

export function userHistoryImageUrl(
  rowId: number,
  kind: "annotated" | "raw" = "annotated",
  token = DEFAULT_AGENT_TOKEN
) {
  const url = new URL(`${AGENT_URL}/api/user/history/${encodeURIComponent(String(rowId))}/image`);
  url.searchParams.set("kind", kind);
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

export function userHistoryExportUrl(rangeDays: AnalyticsRangeDays, token = DEFAULT_AGENT_TOKEN) {
  const url = new URL(`${AGENT_URL}/api/user/history/export.csv`);
  url.searchParams.set("range_days", String(rangeDays));
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

export async function agentFetch<T>(
  path: string,
  init?: RequestInit,
  token = DEFAULT_AGENT_TOKEN
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), AGENT_FETCH_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${AGENT_URL}${path}`, {
      ...init,
      headers,
      cache: "no-store",
      signal: init?.signal ?? controller.signal
    });
  } catch (error) {
    const aborted = error instanceof DOMException && error.name === "AbortError";
    throw new AgentApiError(
      aborted
        ? "Local agent phản hồi quá lâu. Kiểm tra agent hoặc thử lại sau vài giây."
        : "Không kết nối được local agent. Hãy bật agent bằng scripts/start_local.ps1 rồi tải lại web.",
      0
    );
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
  if (!res.ok) {
    const detail = await agentErrorDetail(res);
    throw new AgentApiError(detail || `${res.status} ${res.statusText}`, res.status);
  }
  return (await res.json()) as T;
}

async function agentErrorDetail(res: Response) {
  const text = await res.text();
  if (!text) {
    return "";
  }
  try {
    const parsed = JSON.parse(text) as { detail?: unknown; message?: unknown };
    const detail = parsed.detail ?? parsed.message;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg?: unknown }).msg ?? "");
          }
          return String(item);
        })
        .filter(Boolean)
        .join("; ");
    }
  } catch {
    // Fall through to raw text for non-JSON errors.
  }
  return text;
}
