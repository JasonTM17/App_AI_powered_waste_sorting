"use client";

import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  Camera,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Database,
  Download,
  History,
  ListTree,
  MousePointer2,
  Pencil,
  Play,
  RefreshCcw,
  Recycle,
  Save,
  Search,
  Settings,
  ShieldCheck,
  Square,
  TerminalSquare,
  Trash2,
  Upload,
  Video,
  Wifi,
  X,
  Zap
} from "lucide-react";
import { ChangeEvent, MouseEvent, useEffect, useMemo, useState } from "react";
import {
  AGENT_URL,
  AgentSnapshot,
  ActuationTestMode,
  AppConfig,
  AuthMe,
  ClassMapping,
  CommonWasteItem,
  CaptureSession,
  DEFAULT_AGENT_TOKEN,
  DatasetAnnotationResponse,
  DatasetBox,
  DatasetItem,
  DatasetItemsResponse,
  DatasetSummary,
  Detection,
  HardwareDiagnostics,
  HardwareProfile,
  HardwareTestResponse,
  HistoryRow,
  ModelClass,
  RuntimeStatus,
  TrainingStatus,
  UserDashboard,
  agentFetch,
  datasetImageUrl,
  historyImageUrl,
  streamUrl,
  websocketUrl
} from "@/lib/agent";
import { UserDashboardPanel } from "@/components/user-dashboard-panel";

type TabId = "live" | "history" | "data" | "mapping" | "settings" | "logs";
type TrustedFilter = "all" | "trusted" | "untrusted";
type BulkAction = "delete" | "relabel" | "quarantine" | "mark_trusted" | "mark_untrusted";
type Mp3TestCommand =
  | "TF"
  | "VOL"
  | "PLAY"
  | "PLAYVOL"
  | "NEXT"
  | "ONLINE"
  | "STATUS"
  | "RESET"
  | "MODE_PRIMARY"
  | "MODE_REVERSE"
  | "MODE_QUERY";

type HistoryResponse = {
  rows: HistoryRow[];
  total: number;
};

type LogsResponse = {
  lines: string[];
};

type SettingsResponse = {
  config: AppConfig;
};

type MappingsResponse = {
  mappings: ClassMapping[];
};

type ModelClassesResponse = {
  classes: ModelClass[];
};

type CommonWasteCatalogResponse = {
  items: CommonWasteItem[];
};

type ClassOption = {
  id: number;
  name: string;
};

const DATASET_LIMIT = 60;

const BIN_LABELS: Record<string, string> = {
  O: "Hữu cơ",
  R: "Vô cơ",
  I: "Tái chế"
};

const tabs = [
  { id: "live" as const, label: "Giám sát", icon: Activity },
  { id: "history" as const, label: "Lịch sử", icon: History },
  { id: "data" as const, label: "Dữ liệu", icon: Database },
  { id: "mapping" as const, label: "Mapping", icon: ListTree },
  { id: "settings" as const, label: "Cài đặt", icon: Settings },
  { id: "logs" as const, label: "Nhật ký", icon: TerminalSquare }
];

export function DashboardClient() {
  const [active, setActive] = useState<TabId>("live");
  const [hasHydrated, setHasHydrated] = useState(false);
  const [agentToken, setAgentToken] = useState(DEFAULT_AGENT_TOKEN);
  const [tokenDraft, setTokenDraft] = useState(DEFAULT_AGENT_TOKEN);
  const [auth, setAuth] = useState<AuthMe | null>(null);
  const [userDashboard, setUserDashboard] = useState<UserDashboard | null>(null);
  const [status, setStatus] = useState<RuntimeStatus | null>(null);
  const [summary, setSummary] = useState<DatasetSummary | null>(null);
  const [datasetItems, setDatasetItems] = useState<DatasetItem[]>([]);
  const [datasetTotal, setDatasetTotal] = useState(0);
  const [datasetSource, setDatasetSource] = useState("auto_low_conf");
  const [datasetClass, setDatasetClass] = useState("");
  const [datasetTrusted, setDatasetTrusted] = useState<TrustedFilter>("all");
  const [datasetOffset, setDatasetOffset] = useState(0);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [annotation, setAnnotation] = useState<DatasetAnnotationResponse | null>(null);
  const [annotationBoxes, setAnnotationBoxes] = useState<DatasetBox[]>([]);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [training, setTraining] = useState<TrainingStatus | null>(null);
  const [hardwareProfile, setHardwareProfile] = useState<HardwareProfile | null>(null);
  const [hardwareDiagnostics, setHardwareDiagnostics] = useState<HardwareDiagnostics | null>(null);
  const [hardwareTest, setHardwareTest] = useState<HardwareTestResponse | null>(null);
  const [actuationMode, setActuationMode] = useState<ActuationTestMode | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [mappings, setMappings] = useState<ClassMapping[]>([]);
  const [modelClasses, setModelClasses] = useState<ModelClass[]>([]);
  const [commonWasteItems, setCommonWasteItems] = useState<CommonWasteItem[]>([]);
  const [agentError, setAgentError] = useState("");
  const [notice, setNotice] = useState("");
  const [manualFiles, setManualFiles] = useState<FileList | null>(null);
  const [manualClass, setManualClass] = useState("");
  const [manualImageUrl, setManualImageUrl] = useState("");
  const [manualSourcePageUrl, setManualSourcePageUrl] = useState("");
  const [manualSourceLicense, setManualSourceLicense] = useState("");
  const [manualSourceAuthor, setManualSourceAuthor] = useState("");
  const [captureSession, setCaptureSession] = useState<CaptureSession | null>(null);
  const [importSource, setImportSource] = useState("roboflow");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);

  const cameraStream = useMemo(() => {
    const url = new URL(streamUrl(agentToken));
    url.searchParams.set("v", String(Date.now()));
    return url.toString();
  }, [agentToken, status?.camera.running]);

  const classOptions = useMemo<ClassOption[]>(() => {
    const merged = new Map<string, number>();
    const usedIds = new Set<number>();
    let nextId = 0;
    const allocateId = (preferred?: number) => {
      if (typeof preferred === "number" && preferred >= 0 && !usedIds.has(preferred)) {
        usedIds.add(preferred);
        nextId = Math.max(nextId, preferred + 1);
        return preferred;
      }
      while (usedIds.has(nextId)) {
        nextId += 1;
      }
      const id = nextId;
      usedIds.add(id);
      nextId += 1;
      return id;
    };
    const add = (name: string, preferredId?: number) => {
      const clean = name.trim();
      if (!clean || merged.has(clean)) {
        return;
      }
      merged.set(clean, allocateId(preferredId));
    };
    modelClasses.forEach((item) => add(item.name, item.id));
    commonWasteItems.forEach((item) => add(item.canonical_class, item.class_id ?? undefined));
    mappings.forEach((mapping) => add(mapping.class_name));
    Object.keys(summary?.classes ?? {}).forEach((name) => add(name));
    return [...merged.entries()]
      .map(([name, id]) => ({ id, name }))
      .sort((a, b) => a.id - b.id || a.name.localeCompare(b.name));
  }, [commonWasteItems, mappings, modelClasses, summary?.classes]);

  const normalizedSearch = search.trim().toLowerCase();
  const filteredHistory = useMemo(() => {
    if (!normalizedSearch) {
      return history;
    }
    return history.filter((row) =>
      [row.id, row.ts, row.cls_name, row.route_label, row.bin_index, row.uart_command, row.ack_status]
        .join(" ")
        .toLowerCase()
        .includes(normalizedSearch)
    );
  }, [history, normalizedSearch]);

  const filteredLogs = useMemo(() => {
    if (!normalizedSearch) {
      return logs;
    }
    return logs.filter((line) => line.toLowerCase().includes(normalizedSearch));
  }, [logs, normalizedSearch]);

  function datasetItemsPath() {
    const params = new URLSearchParams({
      limit: String(DATASET_LIMIT),
      offset: String(datasetOffset)
    });
    if (datasetSource) {
      params.set("source", datasetSource);
    }
    if (datasetClass) {
      params.set("cls_name", datasetClass);
    }
    if (datasetTrusted !== "all") {
      params.set("trusted", datasetTrusted === "trusted" ? "true" : "false");
    }
    if (normalizedSearch) {
      params.set("search", normalizedSearch);
    }
    return `/api/dataset/items?${params.toString()}`;
  }

  async function fetchAgent<T>(path: string, init?: RequestInit) {
    return agentFetch<T>(path, init, agentToken);
  }

  async function refreshIdentity(nextToken = agentToken) {
    try {
      const me = await agentFetch<AuthMe>("/api/me", undefined, nextToken);
      setAuth(me);
      setAgentError("");
    } catch (error) {
      setAuth(null);
      setUserDashboard(null);
      setAgentError(error instanceof Error ? error.message : "Khong xac thuc duoc agent");
    }
  }

  async function refreshUserDashboard() {
    setBusy(true);
    try {
      const data = await fetchAgent<UserDashboard>("/api/user/dashboard");
      setUserDashboard(data);
      setAgentError("");
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Khong tai duoc dashboard user");
    } finally {
      setBusy(false);
    }
  }

  function saveAgentToken() {
    const nextToken = tokenDraft.trim();
    setAgentToken(nextToken);
    window.localStorage.setItem("trash-sorter-agent-token", nextToken);
    setNotice("Da cap nhat token");
    void refreshIdentity(nextToken);
  }

  async function refreshAll() {
    try {
      const [
        statusRes,
        trainingRes,
        dataRes,
        itemRes,
        historyRes,
        logsRes,
        settingsRes,
        mappingRes,
        classesRes,
        commonWasteRes,
        hardwareRes,
        hardwareDiagnosticsRes,
        actuationRes
      ] =
        await Promise.all([
          fetchAgent<RuntimeStatus>("/api/status"),
          fetchAgent<TrainingStatus>("/api/training/status"),
          fetchAgent<DatasetSummary>("/api/dataset/summary"),
          fetchAgent<DatasetItemsResponse>(datasetItemsPath()),
          fetchAgent<HistoryResponse>("/api/history?limit=20"),
          fetchAgent<LogsResponse>("/api/logs?limit=120"),
          fetchAgent<SettingsResponse>("/api/settings"),
          fetchAgent<MappingsResponse>("/api/mappings"),
          fetchAgent<ModelClassesResponse>("/api/model/classes"),
          fetchAgent<CommonWasteCatalogResponse>("/api/common-waste/catalog"),
          fetchAgent<HardwareProfile>("/api/hardware/profile"),
          fetchAgent<HardwareDiagnostics>("/api/hardware/diagnostics"),
          fetchAgent<ActuationTestMode>("/api/actuation/test-mode")
        ]);
      setStatus(statusRes);
      setTraining(trainingRes);
      setSummary(dataRes);
      setDatasetItems(itemRes.rows);
      setDatasetTotal(itemRes.total);
      setHistory(historyRes.rows);
      setLogs(logsRes.lines);
      setConfig(settingsRes.config);
      setMappings(mappingRes.mappings);
      setModelClasses(classesRes.classes);
      setCommonWasteItems(commonWasteRes.items);
      setHardwareProfile(hardwareRes);
      setHardwareDiagnostics(hardwareDiagnosticsRes);
      setActuationMode(actuationRes);
      setManualClass((current) => current || classesRes.classes[0]?.name || mappingRes.mappings[0]?.class_name || "");
      setSelectedPaths((current) =>
        current.filter((path) => itemRes.rows.some((item) => item.image_path === path))
      );
      setAgentError("");
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không kết nối được agent");
    }
  }

  async function refreshActive(scope: TabId = active) {
    try {
      const statusPath = scope === "settings" ? "/api/status" : "/api/status?include_devices=false";
      const [statusRes, trainingRes] = await Promise.all([
        fetchAgent<RuntimeStatus>(statusPath),
        fetchAgent<TrainingStatus>("/api/training/status")
      ]);
      setStatus(statusRes);
      setTraining(trainingRes);

      if (scope === "data") {
        const [dataRes, itemRes, classesRes, commonWasteRes, captureSessionRes] = await Promise.all([
          fetchAgent<DatasetSummary>("/api/dataset/summary"),
          fetchAgent<DatasetItemsResponse>(datasetItemsPath()),
          fetchAgent<ModelClassesResponse>("/api/model/classes"),
          fetchAgent<CommonWasteCatalogResponse>("/api/common-waste/catalog"),
          fetchAgent<CaptureSession>("/api/dataset/capture-session")
        ]);
        setSummary(dataRes);
        setDatasetItems(itemRes.rows);
        setDatasetTotal(itemRes.total);
        setModelClasses(classesRes.classes);
        setCommonWasteItems(commonWasteRes.items);
        setCaptureSession(captureSessionRes);
        setManualClass((current) => current || classesRes.classes[0]?.name || "");
        setSelectedPaths((current) =>
          current.filter((path) => itemRes.rows.some((item) => item.image_path === path))
        );
      }

      if (scope === "history") {
        const historyRes = await fetchAgent<HistoryResponse>("/api/history?limit=20");
        setHistory(historyRes.rows);
      }

      if (scope === "logs") {
        const logsRes = await fetchAgent<LogsResponse>("/api/logs?limit=120");
        setLogs(logsRes.lines);
      }

      if (scope === "settings") {
        const [settingsRes, classesRes, commonWasteRes, hardwareRes, hardwareDiagnosticsRes, actuationRes] = await Promise.all([
          fetchAgent<SettingsResponse>("/api/settings"),
          fetchAgent<ModelClassesResponse>("/api/model/classes"),
          fetchAgent<CommonWasteCatalogResponse>("/api/common-waste/catalog"),
          fetchAgent<HardwareProfile>("/api/hardware/profile"),
          fetchAgent<HardwareDiagnostics>("/api/hardware/diagnostics"),
          fetchAgent<ActuationTestMode>("/api/actuation/test-mode")
        ]);
        setConfig(settingsRes.config);
        setModelClasses(classesRes.classes);
        setCommonWasteItems(commonWasteRes.items);
        setHardwareProfile(hardwareRes);
        setHardwareDiagnostics(hardwareDiagnosticsRes);
        setActuationMode(actuationRes);
        setManualClass((current) => current || classesRes.classes[0]?.name || "");
      }

      if (scope === "mapping") {
        const mappingRes = await fetchAgent<MappingsResponse>("/api/mappings");
        setMappings(mappingRes.mappings);
        setManualClass((current) => current || mappingRes.mappings[0]?.class_name || "");
      }
      setAgentError("");
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không kết nối được agent");
    }
  }

  useEffect(() => {
    if (auth?.role !== "admin") {
      return;
    }
    void refreshActive(active);
    const timer = window.setInterval(() => void refreshActive(active), 4000);
    return () => window.clearInterval(timer);
  }, [
    active,
    agentToken,
    auth?.role,
    datasetSource,
    datasetClass,
    datasetTrusted,
    datasetOffset,
    normalizedSearch
  ]);

  useEffect(() => {
    const savedToken = window.localStorage.getItem("trash-sorter-agent-token") ?? DEFAULT_AGENT_TOKEN;
    setAgentToken(savedToken);
    setTokenDraft(savedToken);
    setActive(tabFromLocation());
    setHasHydrated(true);
  }, []);

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }
    void refreshIdentity(agentToken);
  }, [agentToken, hasHydrated]);

  useEffect(() => {
    if (auth?.role !== "user") {
      return;
    }
    void refreshUserDashboard();
    const timer = window.setInterval(() => void refreshUserDashboard(), 4000);
    return () => window.clearInterval(timer);
  }, [agentToken, auth?.role]);

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set("tab", active);
    window.history.replaceState(null, "", url.toString());
  }, [active, hasHydrated]);

  useEffect(() => {
    if (auth?.role !== "admin") {
      return;
    }
    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(websocketUrl(agentToken));
      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data) as AgentSnapshot;
        if (payload.status) {
          setStatus(payload.status);
        }
        if (payload.detections) {
          setDetections(payload.detections);
        }
      };
    } catch {
      socket = null;
    }
    return () => socket?.close();
  }, [agentToken, auth?.role]);

  async function runAction(path: string) {
    setBusy(true);
    try {
      const result = await fetchAgent<{ ok: boolean; message: string }>(path, { method: "POST" });
      setNotice(result.message);
      await refreshActive(active);
    } finally {
      setBusy(false);
    }
  }

  async function refreshDevices() {
    setBusy(true);
    try {
      const nextStatus = await fetchAgent<RuntimeStatus>("/api/devices/refresh", { method: "POST" });
      setStatus(nextStatus);
      setNotice("Đã quét lại thiết bị USB");
      await refreshActive(active);
    } finally {
      setBusy(false);
    }
  }

  async function uploadManualData() {
    if (!manualFiles?.length || !manualClass) {
      return;
    }
    const selectedIndex = classIdForName(manualClass);
    const form = new FormData();
    Array.from(manualFiles).forEach((file) => form.append("files", file));
    form.append("cls_name", manualClass);
    form.append("cls_id", String(selectedIndex));
    setBusy(true);
    try {
      const result = await fetchAgent<{ count: number; message: string }>("/api/dataset/manual", {
        method: "POST",
        body: form
      });
      setNotice(`Đã thêm ${result.count} ảnh thủ công vào CSDL. Mở ảnh mới để vẽ bbox chuẩn.`);
      setDatasetSource("manual_import");
      setDatasetOffset(0);
      await refreshActive(active);
      const latest = await fetchAgent<DatasetItemsResponse>("/api/dataset/items?limit=1&source=manual_import");
      if (latest.rows[0]) {
        await openAnnotation(latest.rows[0].item_id);
      }
    } finally {
      setBusy(false);
    }
  }

  async function captureCameraSample() {
    const className = manualClass.trim();
    if (!className) {
      setNotice("Chua chon class de ghi frame camera");
      return;
    }
    setBusy(true);
    try {
      const result = await fetchAgent<{ count: number; message: string }>("/api/dataset/camera-sample", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cls_name: className,
          cls_id: classIdForName(className),
          use_latest_detection_box: true
        })
      });
      setNotice(result.message);
      setDatasetSource("manual_camera_capture");
      setDatasetOffset(0);
      await refreshActive(active);
      const latest = await fetchAgent<DatasetItemsResponse>("/api/dataset/items?limit=1&source=manual_camera_capture");
      if (latest.rows[0]) {
        await openAnnotation(latest.rows[0].item_id);
      }
    } finally {
      setBusy(false);
    }
  }

  async function startCaptureSession() {
    const className = manualClass.trim();
    if (!className) {
      setNotice("Chua chon class de bat dau phien chup");
      return;
    }
    setBusy(true);
    try {
      const result = await fetchAgent<CaptureSession>("/api/dataset/capture-session/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cls_name: className,
          cls_id: classIdForName(className),
          target_count: 24,
          holdout_count: 6
        })
      });
      setCaptureSession(result);
      setNotice("Da bat dau phien chup. Xoay hoac doi vi tri but truoc moi lan chup.");
    } finally {
      setBusy(false);
    }
  }

  async function captureSessionFrame() {
    setBusy(true);
    try {
      const result = await fetchAgent<CaptureSession>("/api/dataset/capture-session/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pose_index: captureSession?.accepted_count ?? 0,
          use_latest_detection_box: true
        })
      });
      setCaptureSession(result);
      setNotice(result.last_message);
      setDatasetSource("manual_camera_capture");
      setDatasetOffset(0);
      await refreshActive("data");
    } finally {
      setBusy(false);
    }
  }

  async function stopCaptureSession() {
    setBusy(true);
    try {
      const result = await fetchAgent<CaptureSession>("/api/dataset/capture-session/stop", {
        method: "POST"
      });
      setCaptureSession(result);
      setNotice(result.last_message);
    } finally {
      setBusy(false);
    }
  }

  async function importManualImageUrl() {
    const className = manualClass.trim();
    const imageUrl = manualImageUrl.trim();
    if (!className || !imageUrl) {
      setNotice("Can nhap class va URL anh");
      return;
    }
    setBusy(true);
    try {
      const result = await fetchAgent<{ count: number; message: string }>("/api/dataset/manual-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          urls: [imageUrl],
          cls_name: className,
          cls_id: classIdForName(className),
          source_page_url: manualSourcePageUrl.trim(),
          source_license: manualSourceLicense.trim(),
          source_author: manualSourceAuthor.trim()
        })
      });
      setNotice(result.message);
      setDatasetSource("manual_web_import");
      setDatasetOffset(0);
      setManualImageUrl("");
      await refreshActive(active);
      const latest = await fetchAgent<DatasetItemsResponse>("/api/dataset/items?limit=1&source=manual_web_import");
      if (latest.rows[0]) {
        await openAnnotation(latest.rows[0].item_id);
      }
    } finally {
      setBusy(false);
    }
  }

  async function importRoboflowZip(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const form = new FormData();
    form.append("file", file);
    form.append("source_name", importSource);
    setBusy(true);
    try {
      const result = await fetchAgent<{ count: number; message: string }>("/api/dataset/import", {
        method: "POST",
        body: form
      });
      setNotice(`Đã nhập ${result.count} ảnh từ ZIP`);
      setDatasetSource(importSource);
      setDatasetOffset(0);
      await refreshActive(active);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  async function relabelDatasetItem(imagePath: string) {
    await bulkDataset("relabel", [imagePath]);
  }

  async function deleteDatasetItem(imagePath: string) {
    if (!window.confirm("Xóa ảnh này khỏi dataset training?")) {
      return;
    }
    await bulkDataset("delete", [imagePath]);
  }

  async function bulkDataset(action: BulkAction, paths = selectedPaths) {
    if (!paths.length) {
      setNotice("Chưa chọn ảnh nào để thao tác");
      return;
    }
    if (["delete", "quarantine"].includes(action)) {
      const label = action === "delete" ? "xóa" : "cách ly";
      if (!window.confirm(`Bạn muốn ${label} ${paths.length} ảnh đã chọn?`)) {
        return;
      }
    }
    setBusy(true);
    try {
      const result = await fetchAgent<{ count: number; message: string }>("/api/dataset/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          image_paths: paths,
          cls_name: manualClass,
          cls_id: classIdForName(manualClass)
        })
      });
      const actionText: Record<BulkAction, string> = {
        delete: "xóa",
        relabel: `đổi nhãn sang ${manualClass}`,
        quarantine: "cách ly",
        mark_trusted: "đánh dấu sạch",
        mark_untrusted: "đánh dấu cần duyệt"
      };
      setNotice(`Đã ${actionText[action]} ${result.count} ảnh`);
      setSelectedPaths([]);
      await refreshActive(active);
    } finally {
      setBusy(false);
    }
  }

  function classIdForName(name: string) {
    const selected = classOptions.find((item) => item.name === name);
    if (selected) {
      return selected.id;
    }
    return classOptions.reduce((maxId, item) => Math.max(maxId, item.id), -1) + 1;
  }

  async function openAnnotation(itemId: string) {
    setBusy(true);
    try {
      const result = await fetchAgent<DatasetAnnotationResponse>(
        `/api/dataset/items/${encodeURIComponent(itemId)}`
      );
      setAnnotation(result);
      setAnnotationBoxes(result.boxes);
    } finally {
      setBusy(false);
    }
  }

  async function saveAnnotation() {
    if (!annotation) {
      return;
    }
    setBusy(true);
    try {
      const result = await fetchAgent<DatasetAnnotationResponse>(
        `/api/dataset/items/${encodeURIComponent(annotation.item.item_id)}/boxes`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ boxes: annotationBoxes })
        }
      );
      setAnnotation(result);
      setAnnotationBoxes(result.boxes);
      setNotice(`Đã lưu ${result.boxes.length} bbox cho ảnh ${result.item.item_id}`);
      await refreshActive(active);
    } finally {
      setBusy(false);
    }
  }

  async function saveMappings() {
    setBusy(true);
    try {
      const payload = mappings.map((mapping) => ({
        ...mapping,
        command: mapping.command.trim().slice(0, 1).toUpperCase(),
        class_name: mapping.class_name.trim(),
        bin_index: Number(mapping.bin_index)
      }));
      const result = await fetchAgent<MappingsResponse>("/api/mappings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      setMappings(result.mappings);
      setConfig((current) => (current ? { ...current, mappings: result.mappings } : current));
      setNotice("Đã lưu mapping");
      await refreshActive(active);
    } finally {
      setBusy(false);
    }
  }

  async function saveSettings(nextConfig: AppConfig) {
    setBusy(true);
    try {
      const result = await fetchAgent<SettingsResponse>("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(nextConfig)
      });
      setConfig(result.config);
      setNotice("Đã lưu cài đặt");
      await refreshActive(active);
    } finally {
      setBusy(false);
    }
  }

  async function testHardware(command: "O" | "R" | "I") {
    setBusy(true);
    try {
      const result = await fetchAgent<HardwareTestResponse>("/api/hardware/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command })
      });
      setHardwareTest(result);
      setNotice(result.message);
      await refreshActive("settings");
    } finally {
      setBusy(false);
    }
  }

  async function testServoAngles(d6: number, d7: number, label: string) {
    setBusy(true);
    try {
      const result = await fetchAgent<HardwareTestResponse>("/api/hardware/servo-angle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ d6, d7, label })
      });
      setHardwareTest(result);
      setNotice(result.message);
      await refreshActive("settings");
    } finally {
      setBusy(false);
    }
  }

  async function testHomeAngles(d6: number, d7: number, label: string) {
    setBusy(true);
    try {
      const result = await fetchAgent<HardwareTestResponse>("/api/hardware/home-angle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ d6, d7, label })
      });
      setHardwareTest(result);
      setNotice(result.message);
      await refreshActive("settings");
    } finally {
      setBusy(false);
    }
  }

  async function testSortAngles(command: "O" | "R" | "I", d6: number, d7: number, label: string) {
    setBusy(true);
    try {
      const result = await fetchAgent<HardwareTestResponse>("/api/hardware/sort-angle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, d6, d7, label })
      });
      setHardwareTest(result);
      setNotice(result.message);
      await refreshActive("settings");
    } finally {
      setBusy(false);
    }
  }

  async function testAudioTrack(track: number) {
    setBusy(true);
    try {
      const result = await fetchAgent<HardwareTestResponse>("/api/hardware/audio-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track })
      });
      setHardwareTest(result);
      setNotice(result.message);
      await refreshActive("settings");
    } finally {
      setBusy(false);
    }
  }

  async function testMp3(command: Mp3TestCommand, value?: number) {
    setBusy(true);
    try {
      const result = await fetchAgent<HardwareTestResponse>("/api/hardware/mp3-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, value })
      });
      setHardwareTest(result);
      setNotice(result.message);
      await refreshActive("settings");
    } finally {
      setBusy(false);
    }
  }

  async function reconnectHardware() {
    setBusy(true);
    try {
      const result = await fetchAgent<HardwareDiagnostics>("/api/hardware/reconnect", {
        method: "POST"
      });
      setHardwareDiagnostics(result);
      setNotice(result.uart_connected ? "UART da reconnect va san sang" : result.warning || result.uart_message);
      await refreshActive("settings");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActuationTestMode(enabled: boolean) {
    setBusy(true);
    try {
      const result = await fetchAgent<ActuationTestMode>("/api/actuation/test-mode", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled })
      });
      setActuationMode(result);
      setNotice(enabled ? "Da bat Actuation Test Mode" : "Da tat Actuation Test Mode");
      await refreshActive("settings");
    } finally {
      setBusy(false);
    }
  }

  function updateMapping(index: number, patch: Partial<ClassMapping>) {
    setMappings((current) =>
      current.map((mapping, idx) => (idx === index ? { ...mapping, ...patch } : mapping))
    );
  }

  function updateConfig(patch: (cfg: AppConfig) => AppConfig) {
    setConfig((current) => (current ? patch(current) : current));
  }

  function setDatasetSearch(value: string) {
    setSearch(value);
    setDatasetOffset(0);
  }

  function updateDatasetSource(value: string) {
    setDatasetSource(value);
    setDatasetOffset(0);
  }

  function updateDatasetClass(value: string) {
    setDatasetClass(value);
    setDatasetOffset(0);
  }

  function updateDatasetTrusted(value: TrustedFilter) {
    setDatasetTrusted(value);
    setDatasetOffset(0);
  }

  function toggleSelectedPath(path: string) {
    setSelectedPaths((current) =>
      current.includes(path) ? current.filter((item) => item !== path) : [...current, path]
    );
  }

  function toggleAllVisible(checked: boolean) {
    setSelectedPaths((current) => {
      const visible = datasetItems.map((item) => item.image_path);
      if (checked) {
        return Array.from(new Set([...current, ...visible]));
      }
      return current.filter((path) => !visible.includes(path));
    });
  }

  if (auth?.role === "user") {
    return (
      <UserDashboardPanel
        agentError={agentError}
        busy={busy}
        dashboard={userDashboard}
        tokenDraft={tokenDraft}
        onRefresh={() => void refreshUserDashboard()}
        onTokenDraftChange={setTokenDraft}
        onTokenSave={saveAgentToken}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Recycle size={24} />
          </div>
          <div>
            <strong>EcoSort AI</strong>
            <span>Trash Sorter Pro</span>
          </div>
        </div>
        <nav className="nav-list" aria-label="Main navigation">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                className={active === tab.id ? "nav-item active" : "nav-item"}
                onClick={() => setActive(tab.id)}
                type="button"
              >
                <Icon size={18} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="agent-card">
          <span className="eyebrow">Local Agent</span>
          <strong>{AGENT_URL}</strong>
          <div className={agentError ? "system-pill offline" : "system-pill"}>
            <span className="pulse-dot" />
            <span>{agentError ? "Agent offline" : "Hệ thống đang chạy"}</span>
          </div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <label className="search-box" aria-label="Tìm kiếm dữ liệu">
            <Search size={18} />
            <input
              onChange={(event) => setDatasetSearch(event.target.value)}
              placeholder="Tìm data, class, log, đường dẫn..."
              value={search}
            />
          </label>
          <div className="topbar-actions">
            <label className="token-box" aria-label="Role token">
              <ShieldCheck size={17} />
              <input
                onChange={(event) => setTokenDraft(event.target.value)}
                placeholder="Role token"
                type="password"
                value={tokenDraft}
              />
              <button className="round-icon" onClick={saveAgentToken} title="LÆ°u token" type="button">
                <Save size={16} />
              </button>
            </label>
            <button className="round-icon" title="Camera USB" type="button">
              <Video size={19} />
            </button>
            <button className="round-icon" title="AI model" type="button">
              <BrainCircuit size={19} />
            </button>
            <button className="round-icon online" title="Local agent" type="button">
              <Wifi size={19} />
            </button>
            <button
              className="emergency-button"
              disabled={busy}
              onClick={() => void runAction("/api/camera/stop")}
              type="button"
            >
              <AlertTriangle size={17} />
              <span>Dừng hệ thống</span>
            </button>
            <button className="icon-button" onClick={() => void refreshActive(active)} type="button">
              <RefreshCcw size={18} />
              <span>Refresh</span>
            </button>
          </div>
        </header>

        <div className="page-heading">
          <div>
            <span className="eyebrow">USB-only runtime</span>
            <h1>{titleFor(active)}</h1>
            <p>{subtitleFor(active)}</p>
          </div>
          <StatusPill ok={!agentError} text={agentError ? "Agent offline" : "Agent online"} />
        </div>

        {agentError ? <div className="alert">Agent chưa sẵn sàng: {agentError}</div> : null}
        {notice && !agentError ? <div className="success">{notice}</div> : null}

        {active === "live" ? (
          <LivePanel
            busy={busy}
            detections={detections}
            status={status}
            stream={cameraStream}
            training={training}
            onRefreshDevices={() => void refreshDevices()}
            onStart={() => void runAction("/api/camera/start")}
            onStop={() => void runAction("/api/camera/stop")}
          />
        ) : null}
        {active === "history" ? <HistoryPanel imageToken={agentToken} rows={filteredHistory} /> : null}
        {active === "data" ? (
          <DataPanel
            annotation={annotation}
            annotationBoxes={annotationBoxes}
            busy={busy}
            classFilter={datasetClass}
            classOptions={classOptions}
            commonWasteItems={commonWasteItems}
            captureSession={captureSession}
            importSource={importSource}
            itemLimit={DATASET_LIMIT}
            itemOffset={datasetOffset}
            itemTotal={datasetTotal}
            items={datasetItems}
            imageToken={agentToken}
            manualClass={manualClass}
            manualFileCount={manualFiles?.length ?? 0}
            manualImageUrl={manualImageUrl}
            manualSourceAuthor={manualSourceAuthor}
            manualSourceLicense={manualSourceLicense}
            manualSourcePageUrl={manualSourcePageUrl}
            search={normalizedSearch}
            selectedPaths={selectedPaths}
            sourceFilter={datasetSource}
            summary={summary}
            trustedFilter={datasetTrusted}
            onAnnotate={(itemId) => void openAnnotation(itemId)}
            onAnnotationBoxesChange={setAnnotationBoxes}
            onBulk={(action) => void bulkDataset(action)}
            onClassChange={setManualClass}
            onClassFilterChange={updateDatasetClass}
            onCloseAnnotation={() => setAnnotation(null)}
            onDeleteItem={(imagePath) => void deleteDatasetItem(imagePath)}
            onImportSourceChange={setImportSource}
            onImportZip={(event) => void importRoboflowZip(event)}
            onCaptureCameraSample={() => void captureCameraSample()}
            onCaptureSessionFrame={() => void captureSessionFrame()}
            onImageUrlChange={setManualImageUrl}
            onImportImageUrl={() => void importManualImageUrl()}
            onManualFiles={setManualFiles}
            onPage={(nextOffset) => setDatasetOffset(Math.max(0, nextOffset))}
            onRelabelItem={(imagePath) => void relabelDatasetItem(imagePath)}
            onSaveAnnotation={() => void saveAnnotation()}
            onSourceFilterChange={updateDatasetSource}
            onSync={() => void runAction("/api/dataset/sync")}
            onToggleAll={toggleAllVisible}
            onToggleSelected={toggleSelectedPath}
            onTrustedFilterChange={updateDatasetTrusted}
            onSourceAuthorChange={setManualSourceAuthor}
            onSourceLicenseChange={setManualSourceLicense}
            onSourcePageUrlChange={setManualSourcePageUrl}
            onStartCaptureSession={() => void startCaptureSession()}
            onStopCaptureSession={() => void stopCaptureSession()}
            onUpload={() => void uploadManualData()}
          />
        ) : null}
        {active === "mapping" ? (
          <MappingPanel
            busy={busy}
            mappings={mappings}
            search={normalizedSearch}
            onChange={updateMapping}
            onSave={() => void saveMappings()}
          />
        ) : null}
        {active === "settings" ? (
          <SettingsPanel
            actuationMode={actuationMode}
            busy={busy}
            config={config}
            hardwareDiagnostics={hardwareDiagnostics}
            hardwareProfile={hardwareProfile}
            hardwareTest={hardwareTest}
            status={status}
            onChange={updateConfig}
            onRefreshDevices={() => void refreshDevices()}
            onReconnectHardware={() => void reconnectHardware()}
            onSave={(nextConfig) => void saveSettings(nextConfig)}
            onToggleActuationMode={(enabled) => void toggleActuationTestMode(enabled)}
            onTestAudioTrack={(track) => void testAudioTrack(track)}
            onTestHomeAngles={(d6, d7, label) => void testHomeAngles(d6, d7, label)}
            onTestMp3={(command, value) => void testMp3(command, value)}
            onTestServoAngles={(d6, d7, label) => void testServoAngles(d6, d7, label)}
            onTestSortAngles={(command, d6, d7, label) => void testSortAngles(command, d6, d7, label)}
            onTestHardware={(command) => void testHardware(command)}
          />
        ) : null}
        {active === "logs" ? <LogsPanel lines={filteredLogs} /> : null}
      </main>
    </div>
  );
}

function LivePanel({
  busy,
  detections,
  status,
  stream,
  training,
  onRefreshDevices,
  onStart,
  onStop
}: {
  busy: boolean;
  detections: Detection[];
  status: RuntimeStatus | null;
  stream: string;
  training: TrainingStatus | null;
  onRefreshDevices: () => void;
  onStart: () => void;
  onStop: () => void;
}) {
  const trainEpoch =
    training?.completed_epoch && training?.target_epoch
      ? `${training.completed_epoch}/${training.target_epoch}`
      : training?.segment_epoch && training?.segment_epochs
        ? `${training.segment_epoch}/${training.segment_epochs}`
        : training?.running
          ? "Đang chạy"
          : "OFF";
  const trainDetail = training?.map5095 != null
    ? `mAP50-95 ${formatScore(training.map5095)}`
    : training?.message || "Chưa có metric";
  return (
    <section className="content-grid live-grid">
      <div className="stat-row">
        <MetricCard label="Camera" value={status?.camera.running ? "ON" : "OFF"} detail={status?.camera.message} />
        <MetricCard label="FPS" value={formatNumber(status?.fps ?? 0)} detail="Stream realtime" />
        <MetricCard label="Độ trễ" value={`${formatNumber(status?.latency_ms ?? 0)} ms`} detail="Nhận diện" />
        <MetricCard label="UART" value={status?.uart.connected ? "ON" : "OFF"} detail={status?.uart.message} />
        <MetricCard label="Training" value={trainEpoch} detail={trainDetail} />
      </div>

      <div className="camera-panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Live Camera</span>
            <strong>{status?.current_source || "USB camera chưa chọn"}</strong>
          </div>
          <div className="button-row">
            <button className="secondary-button" disabled={busy} onClick={onRefreshDevices} type="button">
              <RefreshCcw size={17} />
              <span>Refresh USB</span>
            </button>
            <button className="primary-button" disabled={busy} onClick={onStart} type="button">
              <Play size={17} />
              <span>Quét USB</span>
            </button>
            <button className="danger-button" disabled={busy} onClick={onStop} type="button">
              <Square size={16} />
              <span>Dừng</span>
            </button>
          </div>
        </div>
        <div className="camera-stage">
          {status?.camera.running ? (
            <>
              <img className="camera-stream" src={stream} alt="USB camera stream" />
              <div className="scan-line" />
              <div className="vision-overlay">
                <ShieldCheck size={16} />
                <span>AI vision online</span>
              </div>
              <DetectionOverlay detections={detections} />
            </>
          ) : (
            <div className="black-frame">
              <Camera size={42} />
              <span>Không có camera USB ngoài hoặc camera đang tắt</span>
            </div>
          )}
        </div>
      </div>

      <div className="side-panel">
        <span className="eyebrow">AI Detection</span>
        <div className="detection-list">
          {detections.length ? (
            detections.slice(0, 8).map((item, index) => (
              <div className="detection-card" key={`${item.timestamp}-${index}`}>
                <div>
                  <strong>{item.cls_name}</strong>
                  <small>
                    {item.route_label || "Chua mapping"} {item.bin_index ? `- thung ${item.bin_index}` : ""}
                  </small>
                  <small>
                    {item.serial_payload ? `Serial: ${item.serial_payload}` : "UART payload: -"}
                    {item.ack ? ` - ${item.ack}` : ""}
                  </small>
                </div>
                <span>{Math.round(item.confidence * 100)}%</span>
              </div>
            ))
          ) : (
            <div className="empty-state">Chưa có detection mới.</div>
          )}
        </div>
      </div>
    </section>
  );
}

function DetectionOverlay({ detections }: { detections: Detection[] }) {
  if (!detections.length) {
    return null;
  }
  return (
    <div className="ai-tags">
      {detections.slice(0, 3).map((item, index) => (
        <div className="ai-tag" key={`${item.timestamp}-overlay-${index}`}>
          <span>{item.cls_name}{item.bin_index ? ` -> thung ${item.bin_index}` : ""}</span>
          <strong>{Math.round(item.confidence * 100)}%</strong>
        </div>
      ))}
    </div>
  );
}

function DataPanel({
  annotation,
  annotationBoxes,
  busy,
  captureSession,
  classFilter,
  classOptions,
  commonWasteItems,
  importSource,
  itemLimit,
  itemOffset,
  itemTotal,
  items,
  imageToken,
  manualClass,
  manualFileCount,
  manualImageUrl,
  manualSourceAuthor,
  manualSourceLicense,
  manualSourcePageUrl,
  search,
  selectedPaths,
  sourceFilter,
  summary,
  trustedFilter,
  onAnnotate,
  onAnnotationBoxesChange,
  onBulk,
  onClassChange,
  onClassFilterChange,
  onCloseAnnotation,
  onDeleteItem,
  onImportSourceChange,
  onImportZip,
  onCaptureCameraSample,
  onCaptureSessionFrame,
  onImageUrlChange,
  onImportImageUrl,
  onManualFiles,
  onPage,
  onRelabelItem,
  onSaveAnnotation,
  onSourceFilterChange,
  onSync,
  onToggleAll,
  onToggleSelected,
  onTrustedFilterChange,
  onSourceAuthorChange,
  onSourceLicenseChange,
  onSourcePageUrlChange,
  onStartCaptureSession,
  onStopCaptureSession,
  onUpload
}: {
  annotation: DatasetAnnotationResponse | null;
  annotationBoxes: DatasetBox[];
  busy: boolean;
  captureSession: CaptureSession | null;
  classFilter: string;
  classOptions: ClassOption[];
  commonWasteItems: CommonWasteItem[];
  importSource: string;
  itemLimit: number;
  itemOffset: number;
  itemTotal: number;
  items: DatasetItem[];
  imageToken: string;
  manualClass: string;
  manualFileCount: number;
  manualImageUrl: string;
  manualSourceAuthor: string;
  manualSourceLicense: string;
  manualSourcePageUrl: string;
  search: string;
  selectedPaths: string[];
  sourceFilter: string;
  summary: DatasetSummary | null;
  trustedFilter: TrustedFilter;
  onAnnotate: (itemId: string) => void;
  onAnnotationBoxesChange: (boxes: DatasetBox[]) => void;
  onBulk: (action: BulkAction) => void;
  onClassChange: (value: string) => void;
  onClassFilterChange: (value: string) => void;
  onCloseAnnotation: () => void;
  onDeleteItem: (imagePath: string) => void;
  onImportSourceChange: (value: string) => void;
  onImportZip: (event: ChangeEvent<HTMLInputElement>) => void;
  onCaptureCameraSample: () => void;
  onCaptureSessionFrame: () => void;
  onImageUrlChange: (value: string) => void;
  onImportImageUrl: () => void;
  onManualFiles: (files: FileList | null) => void;
  onPage: (offset: number) => void;
  onRelabelItem: (imagePath: string) => void;
  onSaveAnnotation: () => void;
  onSourceFilterChange: (value: string) => void;
  onSync: () => void;
  onToggleAll: (checked: boolean) => void;
  onToggleSelected: (path: string) => void;
  onTrustedFilterChange: (value: TrustedFilter) => void;
  onSourceAuthorChange: (value: string) => void;
  onSourceLicenseChange: (value: string) => void;
  onSourcePageUrlChange: (value: string) => void;
  onStartCaptureSession: () => void;
  onStopCaptureSession: () => void;
  onUpload: () => void;
}) {
  const topClasses = Object.entries(summary?.classes ?? {})
    .filter(([name]) => !search || name.toLowerCase().includes(search))
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);
  const rareClasses = Object.entries(summary?.classes ?? {})
    .filter(([, count]) => count < 100)
    .sort((a, b) => a[1] - b[1])
    .slice(0, 10);
  const baseSources = [
    "roboflow",
    "manual_import",
    "manual_camera_capture",
    "manual_web_import",
    "auto_low_conf",
    "unknown",
    "untrusted"
  ];
  const sourceKeys = [
    ...baseSources,
    ...Object.keys(summary?.sources ?? {}).filter((key) => !baseSources.includes(key))
  ];
  const modelClassNames = new Set(classOptions.map((item) => item.name));
  const unknownClasses =
    classOptions.length > 0
      ? Object.entries(summary?.classes ?? {})
          .filter(([name]) => !modelClassNames.has(name))
          .sort((a, b) => b[1] - a[1])
      : [];
  const allVisibleSelected = items.length > 0 && items.every((item) => selectedPaths.includes(item.image_path));
  const pageStart = itemTotal ? itemOffset + 1 : 0;
  const pageEnd = Math.min(itemOffset + itemLimit, itemTotal);

  return (
    <section className="content-grid data-grid">
      <div className="stat-row">
        <MetricCard
          label="Ảnh"
          value={formatNumber(summary?.images ?? 0)}
          detail={`${formatNumber(summary?.trainable_total ?? 0)} sẵn sàng train`}
        />
        <MetricCard
          label="Box"
          value={formatNumber(summary?.boxes ?? 0)}
          detail={`DB: ${formatNumber(summary?.box_catalog_total ?? 0)}`}
        />
        <MetricCard
          label="Class"
          value={formatNumber(classOptions.length || summary?.class_catalog_total || 0)}
          detail={`${formatNumber(summary?.class_catalog_total ?? 0)} trong DB, ${formatNumber(unknownClasses.length)} nhãn lạ`}
        />
        <MetricCard
          label="Dataset DB"
          value={formatNumber(summary?.catalog_total ?? 0)}
          detail={
            summary?.needs_sync
              ? "Cần đồng bộ CSDL"
              : `${formatNumber(summary?.needs_review_total ?? 0)} cần duyệt`
          }
        />
      </div>

      {summary?.needs_sync ? (
        <div className="alert full-span">
          CSDL đang lệch với queue ảnh. Bấm “Đồng bộ CSDL” để cập nhật item và box catalog.
        </div>
      ) : null}

      {unknownClasses.length ? (
        <div className="alert full-span">
          Có {formatNumber(unknownClasses.length)} nhãn ngoài model 42 class đang nằm trong catalog:{" "}
          {unknownClasses.map(([name, count]) => `${name} (${formatNumber(count)})`).join(", ")}.
          Giữ chúng ở trạng thái cần duyệt hoặc map lại trước khi export trainset.
        </div>
      ) : null}

      <div className="panel">
        <div className="panel-toolbar no-pad">
          <div>
            <span className="eyebrow">Nguồn dataset</span>
            <strong>CSDL training</strong>
          </div>
          <div className="button-row">
            <button className="secondary-button" disabled={busy} onClick={onSync} type="button">
              <RefreshCcw size={17} />
              <span>Đồng bộ CSDL</span>
            </button>
          </div>
        </div>
        <div className="source-grid">
          {sourceKeys.map((key) => (
            <button
              className={sourceFilter === key ? "source-tile active" : "source-tile"}
              key={key}
              onClick={() => onSourceFilterChange(sourceFilter === key ? "" : key)}
              type="button"
            >
              <span>{labelSource(key)}</span>
              <strong>{formatNumber(summary?.sources?.[key] ?? 0)}</strong>
            </button>
          ))}
        </div>
        <div className="path-line">Queue: {summary?.queue_dir || "..."}</div>
        <div className="path-line">Catalog: {summary?.catalog_path || "..."}</div>
      </div>

      <div className="panel">
        <span className="eyebrow">Thêm data thủ công</span>
        <div className="capture-note">
          <MousePointer2 size={16} />
          <span>Upload xong web sẽ mở editor để bạn vẽ bbox chuẩn, không cần giữ box toàn ảnh.</span>
        </div>
        {commonWasteItems.length ? (
          <div className="source-grid">
            {commonWasteItems.map((item) => (
              <button
                className={manualClass === item.canonical_class ? "source-tile active" : "source-tile"}
                key={`${item.label}-${item.canonical_class}`}
                onClick={() => onClassChange(item.canonical_class)}
                title={`${item.label} -> ${item.canonical_class} / bin ${item.bin_index}`}
                type="button"
              >
                <span>{item.label}</span>
                <strong>{item.canonical_class}</strong>
              </button>
            ))}
          </div>
        ) : null}
        <div className="form-grid two-col">
          <label>
            Class mặc định
            <input
              list="manual-class-options"
              maxLength={64}
              onChange={(event) => onClassChange(event.target.value)}
              placeholder="Pen, Foam food box, Milk tea cup..."
              value={manualClass}
            />
            <datalist id="manual-class-options">
              {classOptions.map((item) => (
                <option key={`${item.id}-${item.name}`} value={item.name}>
                  {item.name}
                </option>
              ))}
            </datalist>
          </label>
          <label className="file-field">
            Ảnh train
            <span className="file-picker">
              <Upload size={16} />
              <span>{manualFileCount ? `${manualFileCount} ảnh đã chọn` : "Chọn ảnh"}</span>
              <input
                accept="image/*"
                multiple
                onChange={(event) => onManualFiles(event.target.files)}
                type="file"
              />
            </span>
          </label>
        </div>
        <div className="button-row">
          <button
            className="primary-button"
            disabled={busy || !manualClass || manualFileCount === 0}
            onClick={onUpload}
            type="button"
          >
            <Upload size={17} />
            <span>Thêm vào CSDL</span>
          </button>
          <button
            className="secondary-button"
            disabled={busy || !manualClass}
            onClick={onCaptureCameraSample}
            type="button"
          >
            <Camera size={17} />
            <span>Ghi frame camera</span>
          </button>
        </div>
        <div className="capture-note">
          <Camera size={16} />
          <span>
            Phien chup Pen giu Test Mode tat, loai anh mo/trung va tach 6 anh holdout.
          </span>
        </div>
        {captureSession?.session_id ? (
          <div className="class-list">
            <div className="class-row">
              <span>{captureSession.cls_name}</span>
              <strong>
                {captureSession.accepted_count}/{captureSession.target_count}
              </strong>
            </div>
            <div className="class-row">
              <span>Train / holdout</span>
              <strong>
                {captureSession.training_count} / {captureSession.holdout_accepted}
              </strong>
            </div>
            <div className="path-line">{captureSession.last_message}</div>
          </div>
        ) : null}
        <div className="button-row">
          <button
            className="secondary-button"
            disabled={busy || !manualClass || Boolean(captureSession?.active)}
            onClick={onStartCaptureSession}
            type="button"
          >
            <Play size={17} />
            <span>Bat dau 24 anh</span>
          </button>
          <button
            className="primary-button"
            disabled={busy || !captureSession?.active}
            onClick={onCaptureSessionFrame}
            type="button"
          >
            <Camera size={17} />
            <span>Chup tu the tiep theo</span>
          </button>
          <button
            className="secondary-button"
            disabled={busy || !captureSession?.active}
            onClick={onStopCaptureSession}
            type="button"
          >
            <Square size={17} />
            <span>Dung phien</span>
          </button>
        </div>
        <div className="capture-note">
          <Search size={16} />
          <span>URL anh web/Google phai co nguon ro; luu xong can review bbox va quyen su dung truoc khi train.</span>
        </div>
        <div className="form-grid two-col">
          <label>
            URL anh truc tiep
            <input
              maxLength={1000}
              onChange={(event) => onImageUrlChange(event.target.value)}
              placeholder="https://.../image.jpg"
              value={manualImageUrl}
            />
          </label>
          <label>
            Trang nguon
            <input
              maxLength={1000}
              onChange={(event) => onSourcePageUrlChange(event.target.value)}
              placeholder="https://.../bai-viet-hoac-trang-anh"
              value={manualSourcePageUrl}
            />
          </label>
          <label>
            License
            <input
              maxLength={120}
              onChange={(event) => onSourceLicenseChange(event.target.value)}
              placeholder="CC-BY, tu chup, duoc phep dung..."
              value={manualSourceLicense}
            />
          </label>
          <label>
            Tac gia / nguon
            <input
              maxLength={160}
              onChange={(event) => onSourceAuthorChange(event.target.value)}
              placeholder="Ten tac gia, website, hoac ghi chu"
              value={manualSourceAuthor}
            />
          </label>
        </div>
        <button
          className="secondary-button"
          disabled={busy || !manualClass || !manualImageUrl || !manualSourcePageUrl || !manualSourceLicense}
          onClick={onImportImageUrl}
          type="button"
        >
          <Download size={17} />
          <span>Nhap URL vao dataset</span>
        </button>
      </div>

      <div className="panel">
        <span className="eyebrow">Roboflow / YOLO ZIP</span>
        <label className="source-name-field">
          Source name
          <input
            maxLength={48}
            onChange={(event) => onImportSourceChange(event.target.value)}
            placeholder="roboflow_waste_candidate"
            value={importSource}
          />
        </label>
        <label className="drop-zone">
          <Upload size={24} />
          <span>{busy ? "Đang xử lý..." : "Chọn file ZIP đã download từ Roboflow"}</span>
          <input accept=".zip" disabled={busy} onChange={onImportZip} type="file" />
        </label>
      </div>

      <div className="panel class-panel">
        <span className="eyebrow">Top classes</span>
        <div className="class-list">
          {topClasses.length ? (
            topClasses.map(([name, count]) => (
              <div className="class-row" key={name}>
                <span>{name}</span>
                <strong>{formatNumber(count)}</strong>
              </div>
            ))
          ) : (
            <div className="empty-state">Chưa có thống kê class.</div>
          )}
        </div>
        <div className="rare-block">
          <span className="eyebrow">Nên bù thêm data</span>
          <div className="class-list">
            {rareClasses.length ? (
              rareClasses.map(([name, count]) => (
                <div className="class-row rare" key={name}>
                  <span>{name}</span>
                  <strong>{formatNumber(count)}</strong>
                </div>
              ))
            ) : (
              <div className="empty-state">Không có class thiếu nghiêm trọng.</div>
            )}
          </div>
        </div>
      </div>

      <div className="panel full-span">
        <div className="panel-toolbar no-pad">
          <div>
            <span className="eyebrow">Duyệt dataset</span>
            <strong>
              {formatNumber(pageStart)}-{formatNumber(pageEnd)} / {formatNumber(itemTotal)} bản ghi
            </strong>
          </div>
          <span className="muted">Class thao tác: {manualClass || "chưa chọn"}</span>
        </div>

        <div className="filter-grid">
          <label>
            Nguồn
            <select value={sourceFilter} onChange={(event) => onSourceFilterChange(event.target.value)}>
              <option value="">Tất cả nguồn</option>
              {sourceKeys.map((key) => (
                <option key={key} value={key}>
                  {labelSource(key)} ({formatNumber(summary?.sources?.[key] ?? 0)})
                </option>
              ))}
            </select>
          </label>
          <label>
            Class
            <select value={classFilter} onChange={(event) => onClassFilterChange(event.target.value)}>
              <option value="">Tất cả class</option>
              {classOptions.map((item) => (
                <option key={`${item.id}-${item.name}-filter`} value={item.name}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Trạng thái
            <select value={trustedFilter} onChange={(event) => onTrustedFilterChange(event.target.value as TrustedFilter)}>
              <option value="all">Tất cả</option>
              <option value="trusted">Đã tin cậy</option>
              <option value="untrusted">Cần duyệt</option>
            </select>
          </label>
          <div className="pagination-row compact">
            <button
              className="secondary-button compact-button"
              disabled={busy || itemOffset <= 0}
              onClick={() => onPage(itemOffset - itemLimit)}
              type="button"
            >
              <ChevronLeft size={15} />
              <span>Trước</span>
            </button>
            <button
              className="secondary-button compact-button"
              disabled={busy || itemOffset + itemLimit >= itemTotal}
              onClick={() => onPage(itemOffset + itemLimit)}
              type="button"
            >
              <span>Sau</span>
              <ChevronRight size={15} />
            </button>
          </div>
        </div>

        <div className="bulk-toolbar">
          <strong>{formatNumber(selectedPaths.length)} ảnh đã chọn</strong>
          <button
            className="secondary-button compact-button"
            disabled={busy || !selectedPaths.length || !manualClass}
            onClick={() => onBulk("relabel")}
            type="button"
          >
            <Save size={15} />
            <span>Đổi nhãn</span>
          </button>
          <button
            className="secondary-button compact-button"
            disabled={busy || !selectedPaths.length}
            onClick={() => onBulk("mark_trusted")}
            type="button"
          >
            <CheckCircle2 size={15} />
            <span>Mark sạch</span>
          </button>
          <button
            className="secondary-button compact-button"
            disabled={busy || !selectedPaths.length}
            onClick={() => onBulk("mark_untrusted")}
            type="button"
          >
            <AlertTriangle size={15} />
            <span>Cần duyệt</span>
          </button>
          <button
            className="danger-button compact-button"
            disabled={busy || !selectedPaths.length}
            onClick={() => onBulk("quarantine")}
            type="button"
          >
            <AlertTriangle size={15} />
            <span>Cách ly</span>
          </button>
          <button
            className="danger-button compact-button"
            disabled={busy || !selectedPaths.length}
            onClick={() => onBulk("delete")}
            type="button"
          >
            <Trash2 size={15} />
            <span>Xóa</span>
          </button>
        </div>

        <div className="table-wrap">
          <table className="dataset-table">
            <thead>
              <tr>
                <th className="select-col">
                  <input checked={allVisibleSelected} onChange={(event) => onToggleAll(event.target.checked)} type="checkbox" />
                </th>
                <th>Ảnh</th>
                <th>Source</th>
                <th>Class</th>
                <th>Box</th>
                <th>Trust</th>
                <th>Path</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.item_id}>
                  <td className="select-col">
                    <input
                      checked={selectedPaths.includes(item.image_path)}
                      onChange={() => onToggleSelected(item.image_path)}
                      type="checkbox"
                    />
                  </td>
                  <td>
                    <img className="thumb" src={datasetImageUrl(item.item_id, imageToken)} alt="" loading="lazy" />
                  </td>
                  <td>
                    <span className="source-badge">{labelSource(item.source)}</span>
                  </td>
                  <td>{item.cls_name || "-"}</td>
                  <td>{formatNumber(item.box_count)}</td>
                  <td>
                    <StatusPill ok={item.trusted} text={item.trusted ? "Sạch" : "Cần duyệt"} />
                  </td>
                  <td className="table-path" title={item.image_path}>
                    {item.image_path}
                  </td>
                  <td>
                    <div className="row-actions">
                      <button
                        aria-label="Mở bbox editor"
                        className="secondary-button compact-button icon-only"
                        disabled={busy}
                        onClick={() => onAnnotate(item.item_id)}
                        title="Mở bbox editor"
                        type="button"
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        aria-label="Đổi nhãn theo class đang chọn"
                        className="secondary-button compact-button icon-only"
                        disabled={busy || !manualClass}
                        onClick={() => onRelabelItem(item.image_path)}
                        title="Đổi nhãn"
                        type="button"
                      >
                        <Save size={15} />
                      </button>
                      <button
                        aria-label="Xóa ảnh khỏi dataset"
                        className="danger-button compact-button icon-only"
                        disabled={busy}
                        onClick={() => onDeleteItem(item.image_path)}
                        title="Xóa ảnh"
                        type="button"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!items.length ? (
          <div className="empty-state">Chưa có item nào trong catalog hoặc bộ lọc hiện tại không khớp.</div>
        ) : null}
      </div>

      {annotation ? (
        <AnnotationEditor
          annotation={annotation}
          boxes={annotationBoxes}
          busy={busy}
          classOptions={classOptions}
          imageToken={imageToken}
          selectedClass={manualClass}
          onBoxesChange={onAnnotationBoxesChange}
          onClassChange={onClassChange}
          onClose={onCloseAnnotation}
          onSave={onSaveAnnotation}
        />
      ) : null}
    </section>
  );
}

function AnnotationEditor({
  annotation,
  boxes,
  busy,
  classOptions,
  imageToken,
  selectedClass,
  onBoxesChange,
  onClassChange,
  onClose,
  onSave
}: {
  annotation: DatasetAnnotationResponse;
  boxes: DatasetBox[];
  busy: boolean;
  classOptions: ClassOption[];
  imageToken: string;
  selectedClass: string;
  onBoxesChange: (boxes: DatasetBox[]) => void;
  onClassChange: (value: string) => void;
  onClose: () => void;
  onSave: () => void;
}) {
  const [imageSize, setImageSize] = useState({
    width: Math.max(annotation.item.width ?? 1, 1),
    height: Math.max(annotation.item.height ?? 1, 1)
  });
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [draft, setDraft] = useState<DatasetBox | null>(null);
  const activeOption = classOptions.find((item) => item.name === selectedClass) ?? classOptions[0];

  useEffect(() => {
    setImageSize({
      width: Math.max(annotation.item.width ?? 1, 1),
      height: Math.max(annotation.item.height ?? 1, 1)
    });
    setDragStart(null);
    setDraft(null);
  }, [annotation.item.item_id, annotation.item.width, annotation.item.height]);

  function pointFromEvent(event: MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: clamp(((event.clientX - rect.left) / rect.width) * imageSize.width, 0, imageSize.width),
      y: clamp(((event.clientY - rect.top) / rect.height) * imageSize.height, 0, imageSize.height)
    };
  }

  function makeBox(start: { x: number; y: number }, end: { x: number; y: number }): DatasetBox {
    const x1 = Math.min(start.x, end.x);
    const y1 = Math.min(start.y, end.y);
    const x2 = Math.max(start.x, end.x);
    const y2 = Math.max(start.y, end.y);
    return {
      cls_id: activeOption?.id ?? 0,
      cls_name: activeOption?.name ?? selectedClass,
      conf: 1,
      xyxy: [x1, y1, x2, y2]
    };
  }

  function startDraw(event: MouseEvent<HTMLDivElement>) {
    const point = pointFromEvent(event);
    setDragStart(point);
    setDraft(makeBox(point, point));
  }

  function moveDraw(event: MouseEvent<HTMLDivElement>) {
    if (!dragStart) {
      return;
    }
    setDraft(makeBox(dragStart, pointFromEvent(event)));
  }

  function endDraw(event: MouseEvent<HTMLDivElement>) {
    if (!dragStart) {
      return;
    }
    const box = makeBox(dragStart, pointFromEvent(event));
    setDragStart(null);
    setDraft(null);
    if (Math.abs(box.xyxy[2] - box.xyxy[0]) < 6 || Math.abs(box.xyxy[3] - box.xyxy[1]) < 6) {
      return;
    }
    onBoxesChange([...boxes, box]);
  }

  function updateBoxClass(index: number, clsName: string) {
    const option = classOptions.find((item) => item.name === clsName);
    onBoxesChange(
      boxes.map((box, boxIndex) =>
        boxIndex === index
          ? { ...box, cls_id: option?.id ?? box.cls_id, cls_name: option?.name ?? clsName }
          : box
      )
    );
  }

  function updateBoxCoord(index: number, coordIndex: number, raw: number) {
    const next = Number.isFinite(raw) ? raw : 0;
    onBoxesChange(
      boxes.map((box, boxIndex) => {
        if (boxIndex !== index) {
          return box;
        }
        const xyxy = [...box.xyxy] as [number, number, number, number];
        xyxy[coordIndex] = clamp(
          next,
          0,
          coordIndex % 2 === 0 ? imageSize.width : imageSize.height
        );
        return { ...box, xyxy: normalizeBox(xyxy) };
      })
    );
  }

  function removeBox(index: number) {
    onBoxesChange(boxes.filter((_, boxIndex) => boxIndex !== index));
  }

  return (
    <div className="annotation-backdrop" role="dialog" aria-modal="true">
      <div className="annotation-modal">
        <div className="panel-toolbar no-pad">
          <div>
            <span className="eyebrow">Annotation editor</span>
            <strong>{annotation.item.cls_name || annotation.item.item_id}</strong>
          </div>
          <div className="button-row">
            <button className="secondary-button" onClick={onClose} type="button">
              <X size={16} />
              <span>Đóng</span>
            </button>
            <button className="primary-button" disabled={busy} onClick={onSave} type="button">
              <Save size={17} />
              <span>Lưu bbox</span>
            </button>
          </div>
        </div>

        <div className="annotation-layout">
          <div>
            <div
              className="annotation-canvas"
              onMouseDown={startDraw}
              onMouseMove={moveDraw}
              onMouseUp={endDraw}
            >
              <img
                className="annotation-image"
                src={datasetImageUrl(annotation.item.item_id, imageToken)}
                alt={annotation.item.original_file || annotation.item.item_id}
                onLoad={(event) =>
                  setImageSize({
                    width: event.currentTarget.naturalWidth || 1,
                    height: event.currentTarget.naturalHeight || 1
                  })
                }
              />
              {[...boxes, ...(draft ? [draft] : [])].map((box, index) => {
                const style = boxStyle(box, imageSize);
                const isDraft = index >= boxes.length;
                return (
                  <div
                    className={isDraft ? "annotation-box preview" : "annotation-box"}
                    key={`${box.cls_name}-${index}-${box.xyxy.join("-")}`}
                    style={style}
                  >
                    <span>{box.cls_name}</span>
                  </div>
                );
              })}
            </div>
            <p className="muted">Kéo chuột trên ảnh để tạo bbox. Chọn class mặc định trước khi vẽ.</p>
          </div>

          <aside className="annotation-sidebar">
            <label>
              Class mặc định
              <select value={selectedClass} onChange={(event) => onClassChange(event.target.value)}>
                {classOptions.map((item) => (
                  <option key={`${item.id}-${item.name}-draw`} value={item.name}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="annotation-box-list">
              {boxes.length ? (
                boxes.map((box, index) => (
                  <div className="annotation-box-row" key={`${box.cls_name}-${index}`}>
                    <div className="row-actions">
                      <strong>Box {index + 1}</strong>
                      <button className="danger-button compact-button" onClick={() => removeBox(index)} type="button">
                        <Trash2 size={14} />
                      </button>
                    </div>
                    <select value={box.cls_name} onChange={(event) => updateBoxClass(index, event.target.value)}>
                      {classOptions.map((item) => (
                        <option key={`${item.id}-${item.name}-box-${index}`} value={item.name}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                    <div className="mini-grid">
                      {(["x1", "y1", "x2", "y2"] as const).map((label, coordIndex) => (
                        <label key={label}>
                          {label}
                          <input
                            min={0}
                            onChange={(event) => updateBoxCoord(index, coordIndex, Number(event.target.value))}
                            type="number"
                            value={Math.round(box.xyxy[coordIndex])}
                          />
                        </label>
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <div className="empty-state">Chưa có bbox. Kéo trên ảnh để vẽ box đầu tiên.</div>
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function MappingPanel({
  busy,
  mappings,
  search,
  onChange,
  onSave
}: {
  busy: boolean;
  mappings: ClassMapping[];
  search: string;
  onChange: (index: number, patch: Partial<ClassMapping>) => void;
  onSave: () => void;
}) {
  const visibleMappings = mappings
    .map((mapping, index) => ({ mapping, index }))
    .filter(({ mapping }) => !search || mapping.class_name.toLowerCase().includes(search));
  return (
    <section className="panel">
      <div className="panel-toolbar no-pad">
        <div>
          <span className="eyebrow">3 thùng vận hành</span>
          <strong>{formatNumber(mappings.length)} class → Hữu cơ / Tái chế / Vô cơ</strong>
        </div>
        <button className="primary-button" disabled={busy || !mappings.length} onClick={onSave} type="button">
          <Save size={17} />
          <span>Lưu mapping</span>
        </button>
      </div>
      <div className="table-wrap">
        <table className="editable-table">
          <thead>
            <tr>
              <th>Class</th>
              <th>Lệnh</th>
              <th>Thùng</th>
              <th>Nhóm</th>
              <th>Bật</th>
            </tr>
          </thead>
          <tbody>
            {visibleMappings.map(({ mapping, index }) => {
              const command = mapping.command.toUpperCase();
              const binLabel = BIN_LABELS[command] || "Tùy chỉnh";
              return (
                <tr key={`${mapping.class_name}-${index}`}>
                  <td>
                    <input
                      value={mapping.class_name}
                      onChange={(event) => onChange(index, { class_name: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="command-input"
                      maxLength={1}
                      value={mapping.command}
                      onChange={(event) =>
                        onChange(index, { command: event.target.value.slice(0, 1).toUpperCase() })
                      }
                    />
                  </td>
                  <td>
                    <input
                      max={9}
                      min={1}
                      type="number"
                      value={mapping.bin_index}
                      onChange={(event) => onChange(index, { bin_index: Number(event.target.value) })}
                    />
                  </td>
                  <td>
                    <span className={`bin-pill bin-pill-${command.toLowerCase()}`}>{binLabel}</span>
                  </td>
                  <td>
                    <input
                      checked={mapping.enabled}
                      onChange={(event) => onChange(index, { enabled: event.target.checked })}
                      type="checkbox"
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!visibleMappings.length ? <div className="empty-state">Không có mapping khớp bộ lọc hiện tại.</div> : null}
    </section>
  );
}

function SettingsPanel({
  actuationMode,
  busy,
  config,
  hardwareDiagnostics,
  hardwareProfile,
  hardwareTest,
  status,
  onChange,
  onRefreshDevices,
  onReconnectHardware,
  onSave,
  onToggleActuationMode,
  onTestAudioTrack,
  onTestHomeAngles,
  onTestMp3,
  onTestServoAngles,
  onTestSortAngles,
  onTestHardware
}: {
  actuationMode: ActuationTestMode | null;
  busy: boolean;
  config: AppConfig | null;
  hardwareDiagnostics: HardwareDiagnostics | null;
  hardwareProfile: HardwareProfile | null;
  hardwareTest: HardwareTestResponse | null;
  status: RuntimeStatus | null;
  onChange: (patch: (cfg: AppConfig) => AppConfig) => void;
  onRefreshDevices: () => void;
  onReconnectHardware: () => void;
  onSave: (cfg: AppConfig) => void;
  onToggleActuationMode: (enabled: boolean) => void;
  onTestAudioTrack: (track: number) => void;
  onTestHomeAngles: (d6: number, d7: number, label: string) => void;
  onTestMp3: (command: Mp3TestCommand, value?: number) => void;
  onTestServoAngles: (d6: number, d7: number, label: string) => void;
  onTestSortAngles: (command: "O" | "R" | "I", d6: number, d7: number, label: string) => void;
  onTestHardware: (command: "O" | "R" | "I") => void;
}) {
  if (!config) {
    return <div className="empty-state">Đang tải cài đặt...</div>;
  }
  const usbPorts = status?.serial_ports.filter((port) => Boolean(port.is_usb)) ?? [];
  return (
    <section className="content-grid settings-grid">
      <div className="panel">
        <span className="eyebrow">Model</span>
        <div className="form-grid two-col">
          <label>
            Đường dẫn model
            <input
              value={config.model.path}
              onChange={(event) =>
                onChange((cfg) => ({ ...cfg, model: { ...cfg.model, path: event.target.value } }))
              }
            />
          </label>
          <label>
            Thiết bị
            <select
              value={config.model.device}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  model: { ...cfg.model, device: event.target.value as "auto" | "cpu" | "cuda" }
                }))
              }
            >
              <option value="auto">Auto (ưu tiên GPU)</option>
              <option value="cpu">CPU</option>
              <option value="cuda">CUDA</option>
            </select>
          </label>
          <NumberField
            label="Độ tin cậy"
            max={1}
            min={0}
            step={0.01}
            value={config.model.conf_threshold}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, model: { ...cfg.model, conf_threshold: value } }))
            }
          />
          <NumberField
            label="IoU"
            max={1}
            min={0}
            step={0.01}
            value={config.model.iou_threshold}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, model: { ...cfg.model, iou_threshold: value } }))
            }
          />
          <NumberField
            label="Kích thước input"
            min={320}
            step={32}
            value={config.model.input_size}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, model: { ...cfg.model, input_size: Math.round(value) } }))
            }
          />
        </div>
      </div>

      <div className="panel">
        <div className="panel-toolbar no-pad">
          <div>
            <span className="eyebrow">Camera USB</span>
            <strong>{status?.usb_cameras.length ?? 0} thiết bị ngoài</strong>
          </div>
          <button className="secondary-button" disabled={busy} onClick={onRefreshDevices} type="button">
            <RefreshCcw size={17} />
            <span>Refresh USB</span>
          </button>
        </div>
        <div className="policy-strip">
          <Zap size={18} />
          <div>
            <strong>USB only</strong>
            <span>Không fallback webcam máy tính</span>
          </div>
        </div>
        <DeviceList rows={status?.usb_cameras ?? []} empty="Không thấy camera USB ngoài." />
        <div className="form-grid two-col">
          <label>
            Xoay camera
            <select
              value={config.camera.rotation}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  camera: {
                    ...cfg.camera,
                    rotation: Number(event.target.value) as 0 | 90 | 180 | 270
                  }
                }))
              }
            >
              <option value={0}>0° - mốc ban đầu</option>
              <option value={90}>90° phải</option>
              <option value={180}>180°</option>
              <option value={270}>90° trái</option>
            </select>
          </label>
        </div>
      </div>

      <div className="panel">
        <span className="eyebrow">UART USB / Arduino</span>
        {!config.uart.port ? (
          <div className="capture-warning">
            <AlertTriangle size={16} />
            <span>UART OFF, khong gui xuong phan cung. Cam Arduino USB hoac chon dung cong roi luu.</span>
          </div>
        ) : null}
        <div className="form-grid two-col">
          <label>
            Cổng USB
            <select
              value={config.uart.port}
              onChange={(event) =>
                onChange((cfg) => ({ ...cfg, uart: { ...cfg.uart, port: event.target.value } }))
              }
            >
              <option value="">OFF</option>
              {usbPorts.map((port) => (
                <option key={String(port.device)} value={String(port.device)}>
                  {String(port.device)} - {String(port.name || "USB")}
                </option>
              ))}
            </select>
          </label>
          <NumberField
            label="Baud"
            min={1200}
            step={1200}
            value={config.uart.baud}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, uart: { ...cfg.uart, baud: Math.round(value) } }))
            }
          />
          <NumberField
            label="Timeout ACK ms"
            min={10}
            step={10}
            value={config.uart.ack_timeout_ms}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                uart: { ...cfg.uart, ack_timeout_ms: Math.round(value) }
              }))
            }
          />
          <label>
            Giao thức mạch
            <select
              value={config.uart.protocol}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  uart: {
                    ...cfg.uart,
                    protocol: event.target.value as "plain_group" | "sort_line"
                  }
                }))
              }
            >
              <option value="plain_group">Block: huuco / voco / taiche</option>
              <option value="sort_line">Firmware: SORT:O/R/I</option>
            </select>
          </label>
          <label className="check-field">
            <input
              checked={config.uart.auto_reconnect}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  uart: { ...cfg.uart, auto_reconnect: event.target.checked }
                }))
              }
              type="checkbox"
            />
            Tự kết nối lại
          </label>
        </div>
        <DeviceList rows={status?.serial_ports ?? []} empty="Không thấy cổng USB/Arduino." />
      </div>

      <HardwareProfilePanel
        busy={busy}
        diagnostics={hardwareDiagnostics}
        profile={hardwareProfile}
        test={hardwareTest}
        onReconnect={onReconnectHardware}
        onAudioTrackTest={onTestAudioTrack}
        onMp3Test={onTestMp3}
        onHomeAngleTest={onTestHomeAngles}
        onServoAngleTest={onTestServoAngles}
        onSortAngleTest={onTestSortAngles}
        onTest={onTestHardware}
      />

      <div className="panel">
        <span className="eyebrow">ROI / chong lap vong</span>
        <div className="capture-warning">
          <AlertTriangle size={16} />
          <span>Camera chi gui UART khi ROI hop le, khay da trong on dinh va het cooldown.</span>
        </div>
        <div className="form-grid two-col">
          <label className="check-field">
            <input
              checked={config.roi.enabled}
              onChange={(event) =>
                onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, enabled: event.target.checked } }))
              }
              type="checkbox"
            />
            Bat ROI vung khay
          </label>
          <label className="check-field">
            <input
              checked={config.dispatch_guard.require_roi_for_dispatch}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  dispatch_guard: {
                    ...cfg.dispatch_guard,
                    require_roi_for_dispatch: event.target.checked
                  }
                }))
              }
              type="checkbox"
            />
            Bat buoc ROI de do
          </label>
          <NumberField
            label="ROI X"
            min={0}
            step={1}
            value={config.roi.x}
            onValue={(value) => onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, x: Math.round(value) } }))}
          />
          <NumberField
            label="ROI Y"
            min={0}
            step={1}
            value={config.roi.y}
            onValue={(value) => onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, y: Math.round(value) } }))}
          />
          <NumberField
            label="ROI width"
            min={0}
            step={1}
            value={config.roi.width}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, width: Math.round(value) } }))
            }
          />
          <NumberField
            label="ROI height"
            min={0}
            step={1}
            value={config.roi.height}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, height: Math.round(value) } }))
            }
          />
          <NumberField
            label="Cach moi lan do (s)"
            min={0}
            step={0.5}
            value={config.dispatch_guard.min_sort_interval_seconds}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                dispatch_guard: { ...cfg.dispatch_guard, min_sort_interval_seconds: value }
              }))
            }
          />
          <NumberField
            label="Khay trong de re-arm (s)"
            min={0}
            step={0.5}
            value={config.dispatch_guard.empty_rearm_seconds}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                dispatch_guard: { ...cfg.dispatch_guard, empty_rearm_seconds: value }
              }))
            }
          />
        </div>
      </div>

      <ActuationTestModePanel
        busy={busy}
        mode={actuationMode}
        onToggle={onToggleActuationMode}
      />

      <div className="panel">
        <span className="eyebrow">Capture</span>
        <div className={config.capture.mode === "auto_low_conf" ? "capture-warning" : "capture-note"}>
          <AlertTriangle size={16} />
          <span>
            {config.capture.mode === "auto_low_conf"
              ? "Auto low confidence đang tự ghi ảnh vào dataset. Chỉ bật khi bạn đang thu data có kiểm soát."
              : "Capture đang an toàn. Ảnh training chỉ vào CSDL khi bạn thêm thủ công hoặc chủ động bật thu data."}
          </span>
        </div>
        <div className="form-grid two-col">
          <label>
            Chế độ
            <select
              value={config.capture.mode}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  capture: {
                    ...cfg.capture,
                    mode: event.target.value as "off" | "manual" | "auto_low_conf"
                  }
                }))
              }
            >
              <option value="off">Tắt</option>
              <option value="manual">Manual</option>
              <option value="auto_low_conf">Auto low confidence</option>
            </select>
          </label>
          <NumberField
            label="Ngưỡng low confidence"
            max={1}
            min={0}
            step={0.01}
            value={config.capture.low_conf_threshold}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                capture: { ...cfg.capture, low_conf_threshold: value }
              }))
            }
          />
        </div>
        <div className="policy-strip">
          <Wifi size={18} />
          <div>
            <strong>Loa phân loại</strong>
            <span>Đọc đúng 3 nhóm: Hữu cơ, Tái chế, Vô cơ</span>
          </div>
        </div>
        <div className="form-grid two-col">
          <label className="check-field">
            <input
              checked={config.speaker.enabled}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  speaker: { ...cfg.speaker, enabled: event.target.checked }
                }))
              }
              type="checkbox"
            />
            Bật phát loa
          </label>
          <NumberField
            label="Cooldown loa (giây)"
            max={60}
            min={0}
            step={0.5}
            value={config.speaker.cooldown_seconds}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                speaker: { ...cfg.speaker, cooldown_seconds: value }
              }))
            }
          />
        </div>
        <button className="primary-button" disabled={busy} onClick={() => onSave(config)} type="button">
          <Save size={17} />
          <span>Lưu cài đặt</span>
        </button>
      </div>
    </section>
  );
}

function audioSourceLabel(source: unknown) {
  const value = String(source || "").toLowerCase();
  if (value === "sort") {
    return "sort audio";
  }
  if (value === "prox") {
    return "sensor audio";
  }
  if (value === "manual") {
    return "manual test";
  }
  if (value === "startup") {
    return "startup";
  }
  return value || "-";
}

function HardwareProfilePanel({
  busy,
  diagnostics,
  profile,
  test,
  onAudioTrackTest,
  onHomeAngleTest,
  onMp3Test,
  onReconnect,
  onServoAngleTest,
  onSortAngleTest,
  onTest
}: {
  busy: boolean;
  diagnostics: HardwareDiagnostics | null;
  profile: HardwareProfile | null;
  test: HardwareTestResponse | null;
  onAudioTrackTest: (track: number) => void;
  onHomeAngleTest: (d6: number, d7: number, label: string) => void;
  onMp3Test: (command: Mp3TestCommand, value?: number) => void;
  onReconnect: () => void;
  onServoAngleTest: (d6: number, d7: number, label: string) => void;
  onSortAngleTest: (command: "O" | "R" | "I", d6: number, d7: number, label: string) => void;
  onTest: (command: "O" | "R" | "I") => void;
}) {
  if (!profile) {
    return <div className="empty-state">Dang tai mapping phan cung...</div>;
  }
  const waitDegrees = profile.servo.wait_degrees as Record<string, unknown> | undefined;
  const calibration = profile.calibration ?? {};
  const readAngleCandidate = (item: unknown) => {
    const row = item as Record<string, unknown>;
    const d6 = Number(row.D6 ?? row.d6);
    const d7 = Number(row.D7 ?? row.d7);
    if (!Number.isFinite(d6) || !Number.isFinite(d7)) {
      return null;
    }
    const command = String(row.command || "I").toUpperCase();
    return {
      label: String(row.label || `D6=${d6}, D7=${d7}`),
      command: ["O", "R", "I"].includes(command) ? (command as "O" | "R" | "I") : "I",
      d6,
      d7
    };
  };
  const homeCandidates = Array.isArray(calibration.home_candidates)
    ? calibration.home_candidates.map(readAngleCandidate).filter((item) => item !== null)
    : [
        { label: "Home current", command: "I" as const, d6: Number(waitDegrees?.D6 ?? 90), d7: Number(waitDegrees?.D7 ?? 85) },
        { label: "Home D7 -2", command: "I" as const, d6: 90, d7: 83 },
        { label: "Home D7 +2", command: "I" as const, d6: 90, d7: 87 },
        { label: "Home D6 -2", command: "I" as const, d6: 88, d7: 85 },
        { label: "Home D6 +2", command: "I" as const, d6: 92, d7: 85 }
      ];
  const inorganicCandidates = Array.isArray(calibration.inorganic_replay_candidates)
    ? calibration.inorganic_replay_candidates.map(readAngleCandidate).filter((item) => item !== null)
    : [
        { label: "Vo co current", command: "R" as const, d6: 90, d7: 0 },
        { label: "Vo co previous", command: "R" as const, d6: 145, d7: 180 },
        { label: "Vo co max max", command: "R" as const, d6: 180, d7: 180 },
        { label: "Vo co D6 min", command: "R" as const, d6: 0, d7: 180 },
        { label: "Vo co D7 min", command: "R" as const, d6: 180, d7: 0 },
        { label: "Vo co both min", command: "R" as const, d6: 0, d7: 0 },
        { label: "Vo co D6 45", command: "R" as const, d6: 45, d7: 180 },
        { label: "Vo co D7 45", command: "R" as const, d6: 180, d7: 45 }
      ];
  const calibrationPositions = [
    {
      label: "Wait",
      d6: Number(waitDegrees?.D6 ?? 90),
      d7: Number(waitDegrees?.D7 ?? 85)
    },
    ...profile.routes.flatMap((route) => {
      const positions = route.servo_positions as Record<string, unknown> | undefined;
      const d6 = Number(positions?.D6);
      const d7 = Number(positions?.D7);
      if (!Number.isFinite(d6) || !Number.isFinite(d7)) {
        return [];
      }
      return [
        {
          label: String(route.label || route.command || "Route"),
          d6,
          d7
        }
      ];
    })
  ];
  const audioTracks = [
    { label: "Startup", track: Number(profile.gd5800.startup_track ?? 1) },
    { label: "Huu co sort", track: 2 },
    { label: "Vo co sort", track: 3 },
    { label: "Tai che sort", track: 4 },
    { label: "Huu co sensor", track: 5 },
    { label: "Tai che sensor", track: 6 },
    { label: "Vo co sensor", track: 7 }
  ];
  const mp3Tests = [
    { label: "Mode Primary D5/D4", command: "MODE_PRIMARY" as const },
    { label: "Mode Reverse D4/D5", command: "MODE_REVERSE" as const },
    { label: "Mode?", command: "MODE_QUERY" as const },
    { label: "Select TF", command: "TF" as const },
    { label: "TF Online?", command: "ONLINE" as const },
    { label: "Status?", command: "STATUS" as const },
    { label: "Volume 30", command: "VOL" as const, value: 30 },
    { label: "Play 1 index", command: "PLAY" as const, value: 1 },
    { label: "Play 1 + vol", command: "PLAYVOL" as const, value: 1 },
    { label: "Next", command: "NEXT" as const },
    { label: "Reset MP3", command: "RESET" as const }
  ];
  return (
    <div className="panel full-span">
      <div className="panel-toolbar no-pad">
        <div>
          <span className="eyebrow">Mapping phan cung</span>
          <strong>{profile.profile_id || profile.current_port || "UART OFF"}</strong>
          <p className="muted">{profile.uart_message || "Chua co trang thai UART."}</p>
        </div>
        <button
          className="secondary-button"
          disabled={busy}
          onClick={onReconnect}
          type="button"
        >
          <RefreshCcw size={17} />
          <span>Reconnect UART</span>
        </button>
      </div>
      <div className={diagnostics?.warning ? "capture-warning" : "success"}>
        {diagnostics?.warning ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
        <span>
          {diagnostics?.warning ||
            `UART OK; profile ${diagnostics?.firmware_profile || profile.profile_id || "unknown"}`}
        </span>
      </div>
      <div className="hardware-grid">
        {profile.routes.map((route) => {
          const command = String(route.command || "") as "O" | "R" | "I";
          const positions = route.servo_positions
            ? Object.entries(route.servo_positions as Record<string, unknown>)
                .map(([pin, angle]) => `${pin}=${String(angle)}`)
                .join(", ")
            : "";
          return (
            <div className="hardware-route" key={command}>
              <span className={`bin-pill bin-pill-${command.toLowerCase()}`}>{String(route.label || command)}</span>
              <strong>
                {command}
                {" -> "}
                {String(route.serial_payload || "")}
                {"\\n"}
              </strong>
              <small>
                Thung {String(route.bin_index)} - servo {String(route.servo_pin)}
                {positions ? ` (${positions})` : ""} - GD5800 sort track{" "}
                {String(route.gd5800_track)}
              </small>
              <button
                className="secondary-button compact-button"
                disabled={busy || !profile.current_port}
                onClick={() => onTest(command)}
                type="button"
              >
                <MousePointer2 size={15} />
                <span>Test</span>
              </button>
            </div>
          );
        })}
      </div>
      <div className="hardware-meta">
        <div className="policy-strip">
          <MousePointer2 size={18} />
          <div>
            <strong>Home/upright calibration</strong>
            <span>Replay small offsets and choose the one where the tray stands straight, not tilted.</span>
          </div>
        </div>
        <div className="hardware-grid">
          {homeCandidates.map((item) => (
            <button
              className="secondary-button compact-button"
              disabled={busy || !profile.current_port}
              key={`home-${item.label}-${item.d6}-${item.d7}`}
              onClick={() => onHomeAngleTest(item.d6, item.d7, item.label)}
              type="button"
            >
              <MousePointer2 size={15} />
              <span>
                HOME {item.label}: D6={item.d6}, D7={item.d7}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="hardware-meta">
        <div className="policy-strip">
          <MousePointer2 size={18} />
          <div>
            <strong>Tai che direction replay</strong>
            <span>Each button plays track 3, dumps with the candidate angle, then returns to current home.</span>
          </div>
        </div>
        <div className="hardware-grid">
          {inorganicCandidates.map((item) => (
            <button
              className="secondary-button compact-button"
              disabled={busy || !profile.current_port}
              key={`sort-${item.label}-${item.d6}-${item.d7}`}
              onClick={() => onSortAngleTest(item.command, item.d6, item.d7, item.label)}
              type="button"
            >
              <MousePointer2 size={15} />
              <span>
                SORTTEST {item.label}: D6={item.d6}, D7={item.d7}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="hardware-meta">
        <div className="policy-strip">
          <MousePointer2 size={18} />
          <div>
            <strong>Raw servo calibration D6/D7</strong>
            <span>Use raw angle pairs only for inspection; they do not play sort audio.</span>
          </div>
        </div>
        <div className="hardware-grid">
          {calibrationPositions.map((item) => (
            <button
              className="secondary-button compact-button"
              disabled={busy || !profile.current_port}
              key={`${item.label}-${item.d6}-${item.d7}`}
              onClick={() => onServoAngleTest(item.d6, item.d7, item.label)}
              type="button"
            >
              <MousePointer2 size={15} />
              <span>
                {item.label}: D6={item.d6}, D7={item.d7}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="hardware-meta">
        <div className="policy-strip">
          <Zap size={18} />
          <div>
            <strong>GD5800</strong>
            <span>
              Startup track {String(profile.gd5800.startup_track)} - TX {String(profile.gd5800.tx_pin)} - RX{" "}
              {String(profile.gd5800.rx_pin)} - {String(profile.audio_protocol || profile.gd5800.audio_protocol || "audio")} - route audio 2/3/4, sensor audio 5/6/7
            </span>
          </div>
        </div>
        <div className="device-list">
          {(profile.proximity_sensors ?? []).map((sensor) => (
            <div className="device-row" key={String(sensor.pin)}>
              <strong>Cam bien am thanh {String(sensor.label || sensor.command)}</strong>
              <span>
                pin {String(sensor.pin)}, active {String(sensor.active_level)}, track{" "}
                {String(sensor.gd5800_track)}, action {String(sensor.action || "audio_only")}
              </span>
              <StatusPill ok={!sensor.controls_servo} text={sensor.controls_servo ? "servo" : "audio only"} />
            </div>
          ))}
        </div>
        <div className="hardware-grid">
          {mp3Tests.map((item) => (
            <button
              className="secondary-button compact-button"
              disabled={busy || !profile.current_port}
              key={`${item.command}-${item.value ?? ""}`}
              onClick={() => onMp3Test(item.command, item.value)}
              type="button"
            >
              <Zap size={15} />
              <span>
                MP3 {item.label}
              </span>
            </button>
          ))}
        </div>
        <div className="hardware-grid">
          {audioTracks.map((item) => (
            <button
              className="secondary-button compact-button"
              disabled={busy || !profile.current_port}
              key={`${item.label}-${item.track}`}
              onClick={() => onAudioTrackTest(item.track)}
              type="button"
            >
              <Zap size={15} />
              <span>
                Audio {item.track}: {item.label}
              </span>
            </button>
          ))}
        </div>
      </div>
      {diagnostics ? (
        <div className="device-list">
          <div className="device-row">
            <strong>Firmware</strong>
            <span>
              {diagnostics.firmware_profile || "-"}; PONG age{" "}
              {diagnostics.last_pong_age_s ?? "-"}s; profile age{" "}
              {diagnostics.firmware_profile_age_s ?? "-"}s
            </span>
            <StatusPill ok={diagnostics.uart_connected} text={diagnostics.uart_connected ? "connected" : "off"} />
          </div>
          <div className="device-row">
            <strong>Last servo ACK / sensor PROX</strong>
            <span>
              servo ACK {String(diagnostics.last_ack.command || "-")} {String(diagnostics.last_ack.kind || "-")};
              sensor PROX{" "}
              {String(diagnostics.last_proximity.command || "-")}
            </span>
            <StatusPill ok={!diagnostics.disconnect_reason} text={diagnostics.disconnect_reason ? "error" : "clear"} />
          </div>
          <div className="device-row">
            <strong>Current home / routes</strong>
            <span>
              home D6={String(diagnostics.current_home.D6 ?? "-")}, D7={String(diagnostics.current_home.D7 ?? "-")};
              vo co D6={String((diagnostics.current_vo_co ?? diagnostics.current_inorganic).D6 ?? "-")},
              D7={String((diagnostics.current_vo_co ?? diagnostics.current_inorganic).D7 ?? "-")};
              tai che D6={String(diagnostics.current_tai_che?.D6 ?? "-")},
              D7={String(diagnostics.current_tai_che?.D7 ?? "-")};
              firmware home {JSON.stringify(diagnostics.last_servo.detail || {})}
            </span>
            <StatusPill ok={diagnostics.current_home.D6 !== undefined} text="calibration" />
          </div>
          <div className="device-row">
            <strong>Last AUDIO</strong>
            <span>
              cmd {String(diagnostics.last_audio.command || "-")}; track{" "}
              {String(diagnostics.last_audio.track || "-")}; source{" "}
              {audioSourceLabel(diagnostics.last_audio.source)}
            </span>
            <StatusPill
              ok={Boolean(diagnostics.last_audio.track)}
              text={diagnostics.last_audio.track ? audioSourceLabel(diagnostics.last_audio.source) : "none"}
            />
          </div>
          <div className="device-row">
            <strong>Last MP3</strong>
            <span>
              {String(diagnostics.last_mp3.event || "-")}: {String(diagnostics.last_mp3.detail || "-")}
            </span>
            <StatusPill ok={Boolean(diagnostics.last_mp3.event)} text={diagnostics.audio_protocol || "open smart"} />
          </div>
          <div className="device-row">
            <strong>Last MP3 TX</strong>
            <span>{String(diagnostics.last_mp3_tx.detail || "-")}</span>
            <StatusPill ok={Boolean(diagnostics.last_mp3_tx.detail)} text="Arduino -> MP3" />
          </div>
          <div className="device-row">
            <strong>Last MP3 RX</strong>
            <span>{String(diagnostics.last_mp3_rx.detail || "-")}</span>
            <StatusPill ok={Boolean(diagnostics.last_mp3_rx.detail)} text="MP3 -> Arduino" />
          </div>
          {diagnostics.disconnect_reason ? (
            <div className="alert">Disconnect: {diagnostics.disconnect_reason}</div>
          ) : null}
        </div>
      ) : null}
      {test ? (
        <div className={test.ok ? "success" : "alert"}>
          {test.message} - payload {test.payload.trim()} - {test.ack_status || "no_ack"} - {test.elapsed_ms} ms
          {["ANGLE", "HOME", "SORTTEST"].includes(String(test.command || "")) ? ` - ${test.label || "angle"} D6=${test.d6}, D7=${test.d7}` : ""}
          {test.route_command ? ` - route ${test.route_command}` : ""}
          {test.track ? ` - track ${test.track}` : ""}
          {test.value ? ` - value ${test.value}` : ""}
          {test.ok &&
          (test.track ||
            ["TF", "VOL", "PLAY", "PLAYVOL", "NEXT", "ONLINE", "STATUS", "RESET", "MODE_PRIMARY", "MODE_REVERSE", "MODE_QUERY"].includes(
              String(test.command || "")
            )) ? (
            <span> - ACK OK chi xac nhan Arduino da gui lenh MP3; neu khong nghe hay kiem tra microSD, file track, loa, nguon, TX/RX D4-D5.</span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function ActuationTestModePanel({
  busy,
  mode,
  onToggle
}: {
  busy: boolean;
  mode: ActuationTestMode | null;
  onToggle: (enabled: boolean) => void;
}) {
  const enabled = Boolean(mode?.enabled);
  const warning = mode?.warning || "";
  return (
    <div className="panel full-span">
      <div className="panel-toolbar no-pad">
        <div>
          <span className="eyebrow">Actuation Test Mode</span>
          <strong>{enabled ? "Dang bat" : "Dang tat"}</strong>
          <p className="muted">{"Kiem chung camera -> group -> bin -> payload -> ACK -> history."}</p>
        </div>
        <button
          className={enabled ? "danger-button" : "primary-button"}
          disabled={busy}
          onClick={() => onToggle(!enabled)}
          type="button"
        >
          {enabled ? <Square size={17} /> : <ShieldCheck size={17} />}
          <span>{enabled ? "Tat test mode" : "Bat test mode"}</span>
        </button>
      </div>
      {warning ? (
        <div className="capture-warning">
          <AlertTriangle size={16} />
          <span>{warning}</span>
        </div>
      ) : (
        <div className="success">
          <CheckCircle2 size={16} />
          <span>UART connected, san sang ghi nhan ACK khi co dispatch.</span>
        </div>
      )}
      <div className="device-list">
        {(mode?.evidence ?? []).map((item) => (
          <div className="device-row" key={item.history_id}>
            <strong>
              #{item.history_id} {item.detected_class} - {Math.round(item.confidence * 100)}%
            </strong>
            <span>
              {[
                item.route_label || "-",
                `bin ${item.bin_index || "-"}`,
                `cmd ${item.command || "-"}`,
                `payload ${(item.serial_payload || "-").trim()}`,
                item.uart_sent ? "UART sent" : "UART not sent",
                item.ack_status || "-",
                item.timestamp
              ].join(" -> ")}
            </span>
            <StatusPill ok={item.ack_status === "ok"} text={item.ack_status || "pending"} />
          </div>
        ))}
      </div>
      {mode && !mode.evidence.length ? (
        <div className="empty-state">Chua co evidence. Bat camera live va dua tung loai rac vao vung nhan dien.</div>
      ) : null}
    </div>
  );
}

function HistoryPanel({ imageToken, rows }: { imageToken: string; rows: HistoryRow[] }) {
  return (
    <section className="panel">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Thời gian</th>
              <th>Class</th>
              <th>Nhóm</th>
              <th>Thùng</th>
              <th>Độ tin cậy</th>
              <th>UART</th>
              <th>ACK</th>
              <th>Ảnh nhãn</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.id}</td>
                <td>{row.ts}</td>
                <td>{row.cls_name}</td>
                <td>{row.route_label || "-"}</td>
                <td>{row.bin_index || "-"}</td>
                <td>{Math.round(row.conf * 100)}%</td>
                <td>{row.uart_command || "-"}</td>
                <td>{row.ack_status || "-"}</td>
                <td>
                  {row.annotated_path ? (
                    <a
                      className="secondary-button compact-button history-image-link"
                      href={historyImageUrl(row.id, "annotated", imageToken)}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <Camera size={15} />
                      <span>Mở ảnh</span>
                    </a>
                  ) : (
                    "-"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length ? <div className="empty-state">Chưa có lịch sử nhận diện.</div> : null}
    </section>
  );
}

function LogsPanel({ lines }: { lines: string[] }) {
  return (
    <section className="panel">
      <pre className="log-box">{lines.length ? lines.join("\n") : "Chưa có log."}</pre>
    </section>
  );
}

function DeviceList({ rows, empty }: { rows: Array<Record<string, unknown>>; empty: string }) {
  if (!rows.length) {
    return <div className="empty-state">{empty}</div>;
  }
  return (
    <div className="device-list">
      {rows.map((row, index) => {
        const isUsb = Boolean(row.is_usb || row.is_external);
        return (
          <div className={isUsb ? "device-row" : "device-row disabled"} key={index}>
            <strong>{String(row.name || row.device || "Device")}</strong>
            <span>{String(row.hwid || row.instance_id || "")}</span>
            <StatusPill ok={isUsb} text={isUsb ? "USB" : "Đã khóa"} />
          </div>
        );
      })}
    </div>
  );
}

function NumberField({
  label,
  max,
  min,
  step,
  value,
  onValue
}: {
  label: string;
  max?: number;
  min?: number;
  step?: number;
  value: number;
  onValue: (value: number) => void;
}) {
  return (
    <label>
      {label}
      <input
        max={max}
        min={min}
        step={step}
        type="number"
        value={value}
        onChange={(event) => onValue(Number(event.target.value))}
      />
    </label>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="metric-card">
      <span className="eyebrow">{label}</span>
      <strong>{value}</strong>
      <small>{detail || "-"}</small>
    </div>
  );
}

function StatusPill({ ok, text }: { ok: boolean; text: string }) {
  return <span className={ok ? "status-pill ok" : "status-pill warn"}>{text}</span>;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

function formatScore(value: number) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 3,
    minimumFractionDigits: 3
  }).format(value);
}

function titleFor(tab: TabId) {
  return tabs.find((item) => item.id === tab)?.label || "Dashboard";
}

function tabFromLocation(): TabId {
  if (typeof window === "undefined") {
    return "live";
  }
  const raw = new URL(window.location.href).searchParams.get("tab");
  return tabs.some((item) => item.id === raw) ? (raw as TabId) : "live";
}

function subtitleFor(tab: TabId) {
  if (tab === "live") {
    return "Giám sát camera USB, AI detection và trạng thái UART theo thời gian thực";
  }
  if (tab === "history") {
    return "Tra cứu lịch sử nhận diện đã lưu trong history.db";
  }
  if (tab === "data") {
    return "Duyệt auto_low_conf, thêm data thủ công, vẽ bbox và giữ dataset sạch";
  }
  if (tab === "mapping") {
    return "Gán class sang lệnh UART và vị trí thùng phân loại";
  }
  if (tab === "settings") {
    return "Cấu hình model, camera USB-only, UART USB và capture queue";
  }
  return "Theo dõi log local agent và runtime";
}

function labelSource(source: string) {
  if (source === "roboflow") {
    return "Roboflow";
  }
  if (source === "manual_import") {
    return "Thủ công";
  }
  if (source === "manual_camera_capture") {
    return "Camera thu cong";
  }
  if (source === "manual_web_import") {
    return "Anh URL";
  }
  if (source === "auto_low_conf") {
    return "Auto cần duyệt";
  }
  if (source === "untrusted") {
    return "Data lạ";
  }
  if (source === "unknown") {
    return "Unknown";
  }
  return source;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function normalizeBox(xyxy: [number, number, number, number]): [number, number, number, number] {
  return [
    Math.min(xyxy[0], xyxy[2]),
    Math.min(xyxy[1], xyxy[3]),
    Math.max(xyxy[0], xyxy[2]),
    Math.max(xyxy[1], xyxy[3])
  ];
}

function boxStyle(box: DatasetBox, imageSize: { width: number; height: number }) {
  const [x1, y1, x2, y2] = normalizeBox(box.xyxy);
  return {
    left: `${(x1 / imageSize.width) * 100}%`,
    top: `${(y1 / imageSize.height) * 100}%`,
    width: `${((x2 - x1) / imageSize.width) * 100}%`,
    height: `${((y2 - y1) / imageSize.height) * 100}%`
  };
}
