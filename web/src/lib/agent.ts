export type DeviceState = {
  connected: boolean;
  running: boolean;
  message: string;
};

export type RuntimeStatus = {
  camera: DeviceState;
  uart: DeviceState;
  model: DeviceState;
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
  capture: {
    mode: "off" | "manual" | "auto_low_conf";
    low_conf_threshold: number;
    output_dir: string;
  };
  speaker: {
    enabled: boolean;
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

export const AGENT_URL =
  process.env.NEXT_PUBLIC_AGENT_URL?.replace(/\/$/, "") || "http://localhost:8765";

export const DEFAULT_AGENT_TOKEN = process.env.NEXT_PUBLIC_AGENT_TOKEN || "";

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

export async function agentFetch<T>(
  path: string,
  init?: RequestInit,
  token = DEFAULT_AGENT_TOKEN
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetch(`${AGENT_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store"
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}
