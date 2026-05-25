"use client";

import {
  Activity,
  AlertTriangle,
  Bell,
  BrainCircuit,
  CalendarCheck,
  Camera,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Database,
  Download,
  History,
  ListTree,
  MapPin,
  MousePointer2,
  Pencil,
  Play,
  RefreshCcw,
  Save,
  Search,
  Server,
  Settings,
  ShieldCheck,
  Square,
  TerminalSquare,
  Trash2,
  Upload,
  Wifi,
  X,
  Zap
} from "lucide-react";
import { ChangeEvent, MouseEvent, useEffect, useMemo, useRef, useState } from "react";

import { TrashSorterLogo } from "@/components/brand/trash-sorter-logo";
import {
  AGENT_URL,
  AccountDTO,
  AccountsResponse,
  AgentApiError,
  AgentFetchInit,
  AgentSnapshot,
  ActuationTestMode,
  AudioVoicePackStatusResponse,
  AiChatResponse,
  AnalyticsRangeDays,
  AppConfig,
  AuthLoginResponse,
  AuthMe,
  AuthRole,
  AlertsResponse,
  BinMapResponse,
  BinStation,
  BinStationCreatePayload,
  BinStationPatchPayload,
  CameraStreamTokenResponse,
  ClassMapping,
  CommonWasteItem,
  CaptureSession,
  CollectionCompleteResponse,
  CollectionSchedulesResponse,
  DatasetAnnotationResponse,
  DatasetBox,
  DatasetItem,
  DatasetItemsResponse,
  DatasetReviewRequest,
  DatasetSummary,
  Detection,
  DeviceIssueCreatePayload,
  DeviceIssueResponse,
  HardwareDiagnostics,
  HardwareProfile,
  HardwareTestResponse,
  HistoryRow,
  KnowledgeCatalogResponse,
  KnowledgeEntry,
  KnowledgeEvaluateResponse,
  LearnNowStatus,
  ModelClass,
  OperationDevice,
  OperationDevicesResponse,
  OperationDeviceUpsertPayload,
  OperationsHealthResponse,
  RoleCatalogResponse,
  RuntimeStatus,
  SourceQuality,
  TrainingStatus,
  UnknownLearnResponse,
  UserAdvisorResponse,
  UserAnalytics,
  UserDevice,
  UserExperience,
  UserHistoryItem,
  UserHistoryResponse,
  UserReport,
  WebSourceDiscoveryResponse,
  agentFetch,
  datasetImageUrl,
  streamUrl,
  websocketUrl
} from "@/lib/agent";
import { AccountControl } from "@/components/account-control";
import { AdminAccountsPanel } from "@/components/admin-accounts-panel";
import { AuthLoginPanel } from "@/components/auth-login-panel";
import { ManualTrainingPanel } from "@/components/manual-training-panel";
import { RoleChatbotLauncher } from "@/components/chat/role-chatbot-launcher";
import {
  AdminAlertsPanel,
  AdminBinMapPanel,
  AdminDevicesPanel,
  AdminRolesPanel
} from "@/components/operations-panels";
import { PasswordChangePanel } from "@/components/password-change-panel";
import { TopbarStatusControls } from "@/components/topbar-status-controls";
import { UserDashboardPanel } from "@/components/user-dashboard-panel";
import type { UserView } from "@/components/user-dashboard/user-dashboard-types";
import { ActuationTestModePanel } from "@/components/operations/actuation-test-mode-panel";
import { DetectionOverlay } from "@/components/primitives/detection-overlay";
import { DeviceList } from "@/components/primitives/device-list";
import { HistoryPanel } from "@/components/primitives/history-panel";
import { LogsPanel } from "@/components/primitives/logs-panel";
import { StatusPill } from "@/components/primitives/status-pill";
import { AdminReportsPanel } from "@/components/admin/admin-reports-panel";
import { DataPanel } from "@/components/dataset/data-panel";
import type { BulkAction, ClassOption, TrustedFilter } from "@/components/dataset/data-panel-types";
import { AnnotationEditor } from "@/components/dataset/annotation-editor";
import { LivePanel } from "@/components/detection/live-panel";
import { HardwareProfilePanel } from "@/components/operations/hardware-profile-panel";
import { MappingPanel } from "@/components/operations/mapping-panel";
import { SettingsPanel } from "@/components/settings/settings-panel";

type TabId =
  | "live"
  | "history"
  | "data"
  | "training"
  | "mapping"
  | "settings"
  | "logs"
  | "accounts"
  | "roles"
  | "devices"
  | "bin-map"
  | "alerts"
  | "model"
  | "audio"
  | "reports";
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

const DATASET_LIMIT = 60;

const BIN_LABELS: Record<string, string> = {
  O: "Hữu cơ",
  R: "Vô cơ",
  I: "Tái chế"
};

const SESSION_TOKEN_KEY = "trash-sorter-session-token";
const USER_CHATBOT_ENABLED_KEY = "trash-sorter-user-chatbot-enabled";

const tabs = [
  { id: "live" as const, label: "Giám sát", icon: Activity },
  { id: "history" as const, label: "Lịch sử", icon: History },
  { id: "bin-map" as const, label: "Bản đồ", icon: MapPin },
  { id: "alerts" as const, label: "Cảnh báo", icon: Bell },
  { id: "devices" as const, label: "Thiết bị", icon: Server },
  { id: "roles" as const, label: "Role", icon: ShieldCheck },
  { id: "data" as const, label: "Dữ liệu", icon: Database },
  { id: "training" as const, label: "Huấn luyện", icon: BrainCircuit },
  { id: "mapping" as const, label: "Mapping", icon: ListTree },
  { id: "model" as const, label: "Model AI", icon: BrainCircuit },
  { id: "audio" as const, label: "Audio", icon: CalendarCheck },
  { id: "settings" as const, label: "Cài đặt", icon: Settings },
  { id: "logs" as const, label: "Nhật ký", icon: TerminalSquare },
  { id: "accounts" as const, label: "Tài khoản", icon: ShieldCheck },
  { id: "reports" as const, label: "Báo cáo", icon: Download }
];

export function DashboardClient() {
  const [active, setActive] = useState<TabId>("live");
  const [userView, setUserView] = useState<UserView>("dashboard");
  const [hasHydrated, setHasHydrated] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [agentToken, setAgentToken] = useState("");
  const [auth, setAuth] = useState<AuthMe | null>(null);
  const [loginUsername, setLoginUsername] = useState("admin");
  const [loginPassword, setLoginPassword] = useState("");
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [sessionMessage, setSessionMessage] = useState("");
  const [passwordCurrent, setPasswordCurrent] = useState("");
  const [passwordNew, setPasswordNew] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [userAnalytics, setUserAnalytics] = useState<UserAnalytics | null>(null);
  const [userRangeDays, setUserRangeDays] = useState<AnalyticsRangeDays>(30);
  const [userAdvisor, setUserAdvisor] = useState<UserAdvisorResponse | null>(null);
  const [userAdvisorQuestion, setUserAdvisorQuestion] = useState("");
  const [userHistoryRows, setUserHistoryRows] = useState<UserHistoryItem[]>([]);
  const [userDevice, setUserDevice] = useState<UserDevice | null>(null);
  const [userReport, setUserReport] = useState<UserReport | null>(null);
  const [userExperience, setUserExperience] = useState<UserExperience | null>(null);
  const [userBinMap, setUserBinMap] = useState<BinMapResponse | null>(null);
  const [userAlerts, setUserAlerts] = useState<AlertsResponse | null>(null);
  const [userSchedules, setUserSchedules] = useState<CollectionSchedulesResponse | null>(null);
  const [userChat, setUserChat] = useState<AiChatResponse | null>(null);
  const [userChatQuestion, setUserChatQuestion] = useState("");
  const [userChatbotEnabled, setUserChatbotEnabled] = useState(true);
  const [accounts, setAccounts] = useState<AccountDTO[]>([]);
  const [roleCatalog, setRoleCatalog] = useState<RoleCatalogResponse | null>(null);
  const [operationDevices, setOperationDevices] = useState<OperationDevicesResponse | null>(null);
  const [adminBinMap, setAdminBinMap] = useState<BinMapResponse | null>(null);
  const [adminAlerts, setAdminAlerts] = useState<AlertsResponse | null>(null);
  const [adminSchedules, setAdminSchedules] = useState<CollectionSchedulesResponse | null>(null);
  const [operationsHealth, setOperationsHealth] = useState<OperationsHealthResponse | null>(null);
  const [createUsername, setCreateUsername] = useState("");
  const [createPassword, setCreatePassword] = useState("");
  const [createRole, setCreateRole] = useState<AuthRole>("user");
  const [resetPassword, setResetPassword] = useState("");
  const [selectedOwner, setSelectedOwner] = useState("");
  const [adminChat, setAdminChat] = useState<AiChatResponse | null>(null);
  const [adminChatQuestion, setAdminChatQuestion] = useState("");
  const [knowledgeCatalog, setKnowledgeCatalog] = useState<KnowledgeCatalogResponse | null>(null);
  const [knowledgeEvaluation, setKnowledgeEvaluation] = useState<KnowledgeEvaluateResponse | null>(null);
  const [status, setStatus] = useState<RuntimeStatus | null>(null);
  const [summary, setSummary] = useState<DatasetSummary | null>(null);
  const [sourceQuality, setSourceQuality] = useState<SourceQuality | null>(null);
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
  const [cameraStreamTicket, setCameraStreamTicket] = useState("");
  const [learnNow, setLearnNow] = useState<LearnNowStatus | null>(null);
  const [hardwareProfile, setHardwareProfile] = useState<HardwareProfile | null>(null);
  const [voicePackStatus, setVoicePackStatus] = useState<AudioVoicePackStatusResponse | null>(null);
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
  const [manualPhoneFiles, setManualPhoneFiles] = useState<FileList | null>(null);
  const [manualClass, setManualClass] = useState("");
  const [trainingManualClass, setTrainingManualClass] = useState("");
  const [manualImageUrl, setManualImageUrl] = useState("");
  const [manualSourcePageUrl, setManualSourcePageUrl] = useState("");
  const [manualSourceLicense, setManualSourceLicense] = useState("");
  const [manualSourceAuthor, setManualSourceAuthor] = useState("");
  const [manualSourceType, setManualSourceType] = useState("licensed_url");
  const [manualGenerated, setManualGenerated] = useState(false);
  const [unknownHint, setUnknownHint] = useState("");
  const [unknownLearn, setUnknownLearn] = useState<UnknownLearnResponse | null>(null);
  const [webQuery, setWebQuery] = useState("");
  const [webDiscovery, setWebDiscovery] = useState<WebSourceDiscoveryResponse | null>(null);
  const [captureSession, setCaptureSession] = useState<CaptureSession | null>(null);
  const [importSource, setImportSource] = useState("roboflow");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [chatBusy, setChatBusy] = useState(false);

  const cameraStream = useMemo(() => {
    if (!cameraStreamTicket) {
      return "";
    }
    const url = new URL(streamUrl(cameraStreamTicket));
    url.searchParams.set("v", String(Date.now()));
    return url.toString();
  }, [cameraStreamTicket, status?.camera.running]);

  useEffect(() => {
    if (auth?.role !== "admin" || auth.password_default || !status?.camera.running || !agentToken) {
      setCameraStreamTicket("");
      return;
    }
    let cancelled = false;
    async function refreshStreamTicket() {
      try {
        const ticket = await agentFetch<CameraStreamTokenResponse>(
          "/api/camera/stream-token",
          { method: "POST", timeoutMs: 8000 },
          agentToken
        );
        if (!cancelled) {
          setCameraStreamTicket(ticket.token);
        }
      } catch {
        if (!cancelled) {
          setCameraStreamTicket("");
        }
      }
    }
    void refreshStreamTicket();
    const timer = window.setInterval(() => {
      void refreshStreamTicket();
    }, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [agentToken, auth?.role, auth?.password_default, status?.camera.running]);

  useEffect(() => {
    if (!agentToken || !config || (active !== "settings" && active !== "audio" && active !== "model")) {
      return;
    }
    let cancelled = false;
    async function refreshVoicePackStatus() {
      try {
        const gender = config?.speaker.voice_gender ?? "female";
        const statusRes = await fetchAgent<AudioVoicePackStatusResponse>(
          `/api/audio/voice-pack-status?gender=${encodeURIComponent(gender)}`
        );
        if (!cancelled) {
          setVoicePackStatus(statusRes);
        }
      } catch {
        if (!cancelled) {
          setVoicePackStatus(null);
        }
      }
    }
    void refreshVoicePackStatus();
    return () => {
      cancelled = true;
    };
  }, [active, agentToken, config?.speaker.voice_gender]);

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

  function learnNowPath(base = "/api/learn-now/status", rawClass = manualClass) {
    const params = new URLSearchParams();
    const className = canonicalClassForLabel(rawClass) || rawClass.trim();
    if (className) {
      params.set("cls_name", className);
    }
    const query = params.toString();
    return query ? `${base}?${query}` : base;
  }

  function canonicalClassForLabel(raw: string) {
    const clean = raw.trim();
    if (!clean) {
      return "";
    }
    const key = clean.toLowerCase();
    const commonMatch = commonWasteItems.find((item) => {
      const labels = [item.label, item.canonical_class, ...(item.aliases ?? [])].map((value) =>
        value.trim().toLowerCase()
      );
      return labels.includes(key);
    });
    if (commonMatch?.canonical_class) {
      return commonMatch.canonical_class;
    }
    return classOptions.find((item) => item.name.trim().toLowerCase() === key)?.name ?? "";
  }

  function resolveManualClass(raw: string) {
    const className = canonicalClassForLabel(raw);
    if (!className) {
      return null;
    }
    const option = classOptions.find((item) => item.name.trim().toLowerCase() === className.toLowerCase());
    if (!option) {
      return null;
    }
    return { className, classId: option.id };
  }

  async function fetchAgent<T>(path: string, init?: AgentFetchInit) {
    try {
      return await agentFetch<T>(path, init, agentToken);
    } catch (error) {
      if (error instanceof AgentApiError && error.status === 401) {
        setAgentError("Phiên đăng nhập cần được kiểm tra lại. Vui lòng đăng xuất rồi đăng nhập nếu lỗi còn tiếp diễn.");
      }
      throw error;
    }
  }

  async function refreshIdentity(nextToken = agentToken) {
    if (!nextToken) {
      setAuth(null);
      setAgentError("");
      return;
    }
    try {
      const me = await agentFetch<AuthMe>("/api/me", undefined, nextToken);
      setAuth(me);
      setAgentError("");
    } catch (error) {
      if (error instanceof AgentApiError && error.status === 401) {
        clearSession("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
        return;
      }
      setAuth(null);
      setUserAnalytics(null);
      setUserAdvisor(null);
      setAgentError(error instanceof Error ? error.message : "Không xác thực được agent");
    }
  }

  async function loginToAgent() {
    setBusy(true);
    setAgentError("");
    setSessionMessage("");
    try {
      const res = await fetch(`${AGENT_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: loginUsername.trim(),
          password: loginPassword
        }),
        cache: "no-store"
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new AgentApiError(detail || `${res.status} ${res.statusText}`, res.status);
      }
      const data = (await res.json()) as AuthLoginResponse;
      const nextAuth: AuthMe = {
        role: data.role,
        capabilities: data.capabilities,
        auth_required: true,
        account_id: data.account_id,
        username: data.username,
        token_source: "session",
        session_expires_at: data.expires_at,
        password_default: data.password_default
      };
      window.localStorage.setItem(SESSION_TOKEN_KEY, data.token);
      setAgentToken(data.token);
      setAuth(nextAuth);
      setLoginPassword("");
      setNotice("Đã đăng nhập");
      if (data.role === "user") {
        setActive("live");
        setUserView("dashboard");
        window.history.replaceState(null, "", "/user/dashboard");
      } else if (window.location.pathname.startsWith("/user")) {
        window.history.replaceState(null, "", "/admin?tab=live");
      }
    } catch (error) {
      const message =
        error instanceof AgentApiError && error.status === 503
          ? "Chưa cấu hình tài khoản đăng nhập. Hãy bật dev defaults hoặc bootstrap admin."
          : "Sai tài khoản hoặc mật khẩu.";
      setAgentError(error instanceof Error ? error.message : message);
      setSessionMessage(message);
    } finally {
      setBusy(false);
    }
  }

  async function refreshUserDashboard() {
    setBusy(true);
    try {
      const [
        analyticsData,
        historyData,
        deviceData,
        reportData,
        experienceData,
        binMapData,
        alertsData,
        schedulesData
      ] = await Promise.all([
        fetchAgent<UserAnalytics>(`/api/user/analytics?range_days=${userRangeDays}`),
        fetchAgent<UserHistoryResponse>("/api/user/history?limit=24"),
        fetchAgent<UserDevice>("/api/user/device"),
        fetchAgent<UserReport>(`/api/user/report?range_days=${userRangeDays}`),
        fetchAgent<UserExperience>(`/api/user/experience?range_days=${userRangeDays}`),
        fetchAgent<BinMapResponse>("/api/user/bin-map"),
        fetchAgent<AlertsResponse>("/api/user/alerts?include_resolved=false"),
        fetchAgent<CollectionSchedulesResponse>("/api/user/collection-schedule")
      ]);
      setUserAnalytics(analyticsData);
      setUserHistoryRows(historyData.rows);
      setUserDevice(deviceData);
      setUserReport(reportData);
      setUserExperience(experienceData);
      setUserBinMap(binMapData);
      setUserAlerts(alertsData);
      setUserSchedules(schedulesData);
      setAgentError("");
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không tải được dashboard User");
    } finally {
      setBusy(false);
    }
  }

  async function requestUserAdvisor() {
    setBusy(true);
    try {
      const data = await fetchAgent<UserAdvisorResponse>("/api/user/advisor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          range_days: userRangeDays,
          question: userAdvisorQuestion.trim()
        }),
        timeoutMs: 90_000
      });
      setUserAdvisor(data);
      setAgentError("");
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không gọi được AI advisor");
    } finally {
      setBusy(false);
    }
  }

  async function requestUserChat(value?: string) {
    const message = (value ?? userChatQuestion).trim() || "Hôm nay bạn thấy thói quen bỏ rác của mình thế nào?";
    setChatBusy(true);
    try {
      const data = await fetchAgent<AiChatResponse>("/api/user/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
        timeoutMs: 90_000
      });
      setUserChat(data);
      setUserChatQuestion("");
      setAgentError("");
    } catch (error) {
      const fallback = localChatFailure("user", error);
      setUserChat(fallback);
      setNotice(fallback.message);
    } finally {
      setChatBusy(false);
    }
  }

  async function changePassword() {
    setPasswordError("");
    if (passwordNew !== passwordConfirm) {
      setPasswordError("Mật khẩu mới không khớp");
      return;
    }
    if (passwordNew.length < 8) {
      setPasswordError("Mật khẩu mới tối thiểu 8 ký tự");
      return;
    }
    setBusy(true);
    try {
      const nextAuth = await fetchAgent<AuthMe>("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: passwordCurrent,
          new_password: passwordNew
        })
      });
      setAuth(nextAuth);
      setPasswordCurrent("");
      setPasswordNew("");
      setPasswordConfirm("");
      setNotice("Đã đổi mật khẩu");
    } catch (error) {
      setPasswordError(error instanceof Error ? error.message : "Không đổi được mật khẩu");
    } finally {
      setBusy(false);
    }
  }

  async function refreshAccounts() {
    const data = await fetchAgent<AccountsResponse>("/api/admin/accounts");
    setAccounts(data.accounts);
    setSelectedOwner((current) => current || data.accounts.find((account) => account.role === "user")?.username || "");
  }

  async function refreshKnowledge() {
    const data = await fetchAgent<KnowledgeCatalogResponse>("/api/admin/knowledge");
    setKnowledgeCatalog(data);
  }

  async function refreshAdminOperations() {
    const [rolesData, devicesData, binMapData, alertsData, schedulesData, healthData] = await Promise.all([
      fetchAgent<RoleCatalogResponse>("/api/admin/roles"),
      fetchAgent<OperationDevicesResponse>("/api/admin/devices"),
      fetchAgent<BinMapResponse>("/api/admin/bin-map", { timeoutMs: 45_000 }),
      fetchAgent<AlertsResponse>("/api/admin/alerts?include_resolved=false", { timeoutMs: 45_000 }),
      fetchAgent<CollectionSchedulesResponse>("/api/admin/collection-schedules", { timeoutMs: 45_000 }),
      fetchAgent<OperationsHealthResponse>("/api/admin/operations/health", { timeoutMs: 45_000 })
    ]);
    setRoleCatalog(rolesData);
    setOperationDevices(devicesData);
    setAdminBinMap(binMapData);
    setAdminAlerts(alertsData);
    setAdminSchedules(schedulesData);
    setOperationsHealth(healthData);
  }

  async function refreshUserOperations() {
    const [binMapData, alertsData, schedulesData] = await Promise.all([
      fetchAgent<BinMapResponse>("/api/user/bin-map", { timeoutMs: 45_000 }),
      fetchAgent<AlertsResponse>("/api/user/alerts?include_resolved=false", { timeoutMs: 45_000 }),
      fetchAgent<CollectionSchedulesResponse>("/api/user/collection-schedule", { timeoutMs: 45_000 })
    ]);
    setUserBinMap(binMapData);
    setUserAlerts(alertsData);
    setUserSchedules(schedulesData);
  }

  async function saveOperationDevice(payload: OperationDeviceUpsertPayload) {
    setBusy(true);
    try {
      await fetchAgent<OperationDevice>("/api/admin/devices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      setNotice("Đã lưu thiết bị.");
      await refreshAdminOperations();
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không lưu được thiết bị");
    } finally {
      setBusy(false);
    }
  }

  async function createBinStation(payload: BinStationCreatePayload) {
    setBusy(true);
    try {
      await fetchAgent<BinStation>("/api/admin/bin-map", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      setNotice("Đã tạo trạm thùng rác.");
      await refreshAdminOperations();
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không tạo được trạm thùng rác");
    } finally {
      setBusy(false);
    }
  }

  async function patchBinStation(stationId: string, payload: BinStationPatchPayload) {
    setBusy(true);
    try {
      await fetchAgent<BinStation>(`/api/admin/bin-map/${encodeURIComponent(stationId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      setNotice("Đã cập nhật tọa độ trạm.");
      await refreshAdminOperations();
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không cập nhật được trạm");
    } finally {
      setBusy(false);
    }
  }

  async function deleteBinStation(stationId: string) {
    setBusy(true);
    try {
      await fetchAgent(`/api/admin/bin-map/${encodeURIComponent(stationId)}`, { method: "DELETE" });
      setNotice("Đã ngưng hoạt động trạm.");
      await refreshAdminOperations();
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không ngưng hoạt động được trạm");
    } finally {
      setBusy(false);
    }
  }

  async function patchOperationAlert(alertId: string, statusValue: "open" | "acknowledged" | "resolved") {
    setBusy(true);
    try {
      await fetchAgent<AlertsResponse>(`/api/admin/alerts/${encodeURIComponent(alertId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: statusValue })
      });
      setNotice(statusValue === "resolved" ? "Đã xử lý cảnh báo." : "Đã cập nhật cảnh báo.");
      await refreshAdminOperations();
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không cập nhật được cảnh báo");
    } finally {
      setBusy(false);
    }
  }

  async function completeCollection(scheduleId: string, note: string) {
    setBusy(true);
    try {
      const result = await fetchAgent<CollectionCompleteResponse>(
        `/api/user/collections/${encodeURIComponent(scheduleId)}/complete`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ note })
        }
      );
      setNotice(result.already_completed ? "Lịch này đã được đánh dấu trước đó." : "Đã đánh dấu đã thu gom.");
      await refreshUserOperations();
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không đánh dấu thu gom được");
    } finally {
      setBusy(false);
    }
  }

  async function reportDeviceIssue(payload: DeviceIssueCreatePayload) {
    setBusy(true);
    try {
      await fetchAgent<DeviceIssueResponse>("/api/user/device-issues", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      setNotice("Đã gửi báo lỗi thiết bị và tạo cảnh báo.");
      await refreshUserOperations();
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không gửi được báo lỗi thiết bị");
    } finally {
      setBusy(false);
    }
  }

  async function upsertKnowledge(payload: {
    id?: string;
    title: string;
    roles: AuthRole[];
    keywords: string[];
    text: string;
    enabled: boolean;
  }) {
    setBusy(true);
    try {
      const data = await fetchAgent<KnowledgeCatalogResponse>("/api/admin/knowledge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      setKnowledgeCatalog(data);
      setNotice("Đã cập nhật knowledge cho trợ lý AI.");
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không cập nhật được knowledge");
    } finally {
      setBusy(false);
    }
  }

  async function patchKnowledge(entry: KnowledgeEntry, patch: Partial<Pick<KnowledgeEntry, "enabled">>) {
    setBusy(true);
    try {
      const data = await fetchAgent<KnowledgeCatalogResponse>(`/api/admin/knowledge/${encodeURIComponent(entry.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch)
      });
      setKnowledgeCatalog(data);
      setNotice(patch.enabled === false ? "Đã tắt snippet knowledge." : "Đã bật snippet knowledge.");
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không chỉnh được knowledge");
    } finally {
      setBusy(false);
    }
  }

  async function reloadKnowledge() {
    setBusy(true);
    try {
      const data = await fetchAgent<KnowledgeCatalogResponse>("/api/admin/knowledge/reload", { method: "POST" });
      setKnowledgeCatalog(data);
      setNotice("Đã nạp lại knowledge pack.");
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không nạp lại được knowledge");
    } finally {
      setBusy(false);
    }
  }

  async function evaluateKnowledge(question: string, role: AuthRole) {
    setBusy(true);
    try {
      const data = await fetchAgent<KnowledgeEvaluateResponse>("/api/admin/knowledge/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, role })
      });
      setKnowledgeEvaluation(data);
      setNotice("Đã chạy kiểm thử retrieval.");
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không kiểm thử được knowledge");
    } finally {
      setBusy(false);
    }
  }

  async function createAccount() {
    setBusy(true);
    try {
      await fetchAgent<AccountDTO>("/api/admin/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: createUsername.trim(),
          password: createPassword,
          role: createRole
        })
      });
      setCreateUsername("");
      setCreatePassword("");
      setNotice("Đã tạo tài khoản. Tài khoản mới sẽ bị bắt đổi mật khẩu khi đăng nhập.");
      await refreshAccounts();
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không tạo được tài khoản");
    } finally {
      setBusy(false);
    }
  }

  async function resetAccountPassword(username: string) {
    setBusy(true);
    try {
      await fetchAgent<AccountDTO>(`/api/admin/accounts/${encodeURIComponent(username)}/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: resetPassword })
      });
      setResetPassword("");
      setNotice(`Đã đặt lại mật khẩu cho ${username}`);
      await refreshAccounts();
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không đặt lại được mật khẩu");
    } finally {
      setBusy(false);
    }
  }

  async function toggleAccountActive(username: string, activeValue: boolean) {
    setBusy(true);
    try {
      await fetchAgent<AccountDTO>(`/api/admin/accounts/${encodeURIComponent(username)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: activeValue })
      });
      setNotice(activeValue ? "Đã kích hoạt tài khoản" : "Đã vô hiệu tài khoản");
      await refreshAccounts();
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không cập nhật được tài khoản");
    } finally {
      setBusy(false);
    }
  }

  async function backfillOwner() {
    if (!selectedOwner) {
      return;
    }
    setBusy(true);
    try {
      const result = await fetchAgent<{ ok: boolean; message: string; count: number }>(
        `/api/admin/history/backfill-owner?owner_username=${encodeURIComponent(selectedOwner)}`,
        { method: "POST" }
      );
      setNotice(`${result.message}: ${result.count} rows`);
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : "Không gán chủ sở hữu cho lịch sử được");
    } finally {
      setBusy(false);
    }
  }

  async function requestAdminChat(value?: string) {
    const message = (value ?? adminChatQuestion).trim() || "Tóm tắt hệ thống hôm nay.";
    setChatBusy(true);
    try {
      const data = await fetchAgent<AiChatResponse>("/api/admin/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
        timeoutMs: 90_000
      });
      setAdminChat(data);
      setAdminChatQuestion("");
      setAgentError("");
    } catch (error) {
      const fallback = localChatFailure("admin", error);
      setAdminChat(fallback);
      setNotice(fallback.message);
    } finally {
      setChatBusy(false);
    }
  }

  async function logoutFromAgent() {
    const token = agentToken;
    clearSession("");
    if (token) {
      try {
        await agentFetch("/api/auth/logout", { method: "POST" }, token);
      } catch {
        // Logout is best-effort because the local session is already cleared.
      }
    }
    setNotice("Đã đăng xuất");
  }

  function clearSession(message: string) {
    window.localStorage.removeItem(SESSION_TOKEN_KEY);
    setAgentToken("");
    setAuth(null);
    setStatus(null);
    setDetections([]);
    setUserAnalytics(null);
    setUserAdvisor(null);
    setUserHistoryRows([]);
    setUserDevice(null);
    setUserReport(null);
    setUserExperience(null);
    setUserBinMap(null);
    setUserAlerts(null);
    setUserSchedules(null);
    setUserChat(null);
    setAdminChat(null);
    setKnowledgeCatalog(null);
    setKnowledgeEvaluation(null);
    setAccounts([]);
    setRoleCatalog(null);
    setOperationDevices(null);
    setAdminBinMap(null);
    setAdminAlerts(null);
    setAdminSchedules(null);
    setOperationsHealth(null);
    setPasswordCurrent("");
    setPasswordNew("");
    setPasswordConfirm("");
    setPasswordError("");
    setSessionMessage(message);
    setAgentError("");
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
        learnNowRes,
        sourceQualityRes,
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
          fetchAgent<LearnNowStatus>(learnNowPath()),
          fetchAgent<SourceQuality>("/api/dataset/source-quality"),
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
      setLearnNow(learnNowRes);
      setSourceQuality(sourceQualityRes);
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

  async function refreshActive(scope: TabId = active, signal?: AbortSignal) {
    const scopedFetch = <T,>(path: string, init: AgentFetchInit = {}) =>
      fetchAgent<T>(path, { ...init, signal });
    try {
      const settingsLike = scope === "settings" || scope === "model" || scope === "audio";
      const operationsLike = scope === "roles" || scope === "devices" || scope === "bin-map" || scope === "alerts";
      const dataLike = scope === "data";
      const trainingLike = scope === "training";
      const statusPath = settingsLike ? "/api/status" : "/api/status?include_devices=false";
      const statusRes = await scopedFetch<RuntimeStatus>(statusPath);
      setStatus(statusRes);

      if (dataLike) {
        const [dataRes, itemRes, classesRes, commonWasteRes, sourceQualityRes] = await Promise.all([
          scopedFetch<DatasetSummary>("/api/dataset/summary"),
          scopedFetch<DatasetItemsResponse>(datasetItemsPath()),
          scopedFetch<ModelClassesResponse>("/api/model/classes"),
          scopedFetch<CommonWasteCatalogResponse>("/api/common-waste/catalog"),
          scopedFetch<SourceQuality>("/api/dataset/source-quality")
        ]);
        setSummary(dataRes);
        setDatasetItems(itemRes.rows);
        setDatasetTotal(itemRes.total);
        setModelClasses(classesRes.classes);
        setCommonWasteItems(commonWasteRes.items);
        setSourceQuality(sourceQualityRes);
        setManualClass((current) => current || classesRes.classes[0]?.name || "");
        setSelectedPaths((current) =>
          current.filter((path) => itemRes.rows.some((item) => item.image_path === path))
        );
      }

      if (trainingLike) {
        const [trainingRes, classesRes, commonWasteRes, captureSessionRes, learnNowRes] = await Promise.all([
          scopedFetch<TrainingStatus>("/api/training/status"),
          scopedFetch<ModelClassesResponse>("/api/model/classes"),
          scopedFetch<CommonWasteCatalogResponse>("/api/common-waste/catalog"),
          scopedFetch<CaptureSession>("/api/dataset/capture-session"),
          scopedFetch<LearnNowStatus>(learnNowPath("/api/learn-now/status", trainingManualClass), {
            timeoutMs: 30_000
          })
        ]);
        setTraining(trainingRes);
        setModelClasses(classesRes.classes);
        setCommonWasteItems(commonWasteRes.items);
        setCaptureSession(captureSessionRes);
        setLearnNow(learnNowRes);
      }

      if (scope === "history") {
        const historyRes = await scopedFetch<HistoryResponse>("/api/history?limit=20");
        setHistory(historyRes.rows);
      }

      if (scope === "reports") {
        const [historyRes, dataRes, sourceQualityRes] = await Promise.all([
          scopedFetch<HistoryResponse>("/api/history?limit=20"),
          scopedFetch<DatasetSummary>("/api/dataset/summary"),
          scopedFetch<SourceQuality>("/api/dataset/source-quality")
        ]);
        setHistory(historyRes.rows);
        setSummary(dataRes);
        setSourceQuality(sourceQualityRes);
      }

      if (scope === "logs") {
        const logsRes = await scopedFetch<LogsResponse>("/api/logs?limit=120");
        setLogs(logsRes.lines);
      }

      if (settingsLike) {
        const [settingsRes, classesRes, commonWasteRes, hardwareRes, hardwareDiagnosticsRes, actuationRes] = await Promise.all([
          scopedFetch<SettingsResponse>("/api/settings"),
          scopedFetch<ModelClassesResponse>("/api/model/classes"),
          scopedFetch<CommonWasteCatalogResponse>("/api/common-waste/catalog"),
          scopedFetch<HardwareProfile>("/api/hardware/profile"),
          scopedFetch<HardwareDiagnostics>("/api/hardware/diagnostics"),
          scopedFetch<ActuationTestMode>("/api/actuation/test-mode")
        ]);
        setConfig(settingsRes.config);
        setModelClasses(classesRes.classes);
        setCommonWasteItems(commonWasteRes.items);
        setHardwareProfile(hardwareRes);
        setHardwareDiagnostics(hardwareDiagnosticsRes);
        setActuationMode(actuationRes);
        setVoicePackStatus(
          await scopedFetch<AudioVoicePackStatusResponse>(
            `/api/audio/voice-pack-status?gender=${encodeURIComponent(settingsRes.config.speaker.voice_gender ?? "female")}`
          )
        );
        setManualClass((current) => current || classesRes.classes[0]?.name || "");
      }

      if (scope === "mapping") {
        const mappingRes = await scopedFetch<MappingsResponse>("/api/mappings");
        setMappings(mappingRes.mappings);
        setManualClass((current) => current || mappingRes.mappings[0]?.class_name || "");
      }

      if (scope === "accounts") {
        await Promise.all([refreshAccounts(), refreshKnowledge()]);
      }

      if (operationsLike) {
        await refreshAdminOperations();
      }
      setAgentError("");
    } catch (error) {
      if (signal?.aborted) {
        return;
      }
      setAgentError(error instanceof Error ? error.message : "Không kết nối được agent");
    }
  }

  useEffect(() => {
    if (auth?.role !== "admin" || auth.password_default) {
      return;
    }
    const pollingIntervalMs =
      active === "bin-map" || active === "alerts" || active === "roles" || active === "devices" || active === "training"
        ? 12_000
        : 4_000;
    const controller = new AbortController();
    let refreshInFlight = false;
    const runRefresh = async () => {
      if (refreshInFlight || chatBusy || document.visibilityState === "hidden") {
        return;
      }
      refreshInFlight = true;
      try {
        await refreshActive(active, controller.signal);
      } finally {
        refreshInFlight = false;
      }
    };
    void runRefresh();
    const timer = window.setInterval(() => void runRefresh(), pollingIntervalMs);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [
    active,
    agentToken,
    auth?.role,
    auth?.password_default,
    chatBusy,
    datasetSource,
    datasetClass,
    datasetTrusted,
    datasetOffset,
    manualClass,
    trainingManualClass,
    normalizedSearch
  ]);

  useEffect(() => {
    const savedToken = window.localStorage.getItem(SESSION_TOKEN_KEY) ?? "";
    const savedChatbot = window.localStorage.getItem(USER_CHATBOT_ENABLED_KEY);
    setAgentToken(savedToken);
    setUserChatbotEnabled(savedChatbot !== "0");
    setActive(tabFromLocation());
    setUserView(userViewFromLocation());
    setHasHydrated(true);
  }, []);

  function updateUserChatbotEnabled(enabled: boolean) {
    setUserChatbotEnabled(enabled);
    window.localStorage.setItem(USER_CHATBOT_ENABLED_KEY, enabled ? "1" : "0");
  }

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }
    if (!agentToken) {
      setAuth(null);
      return;
    }
    void refreshIdentity(agentToken);
  }, [agentToken, hasHydrated]);

  useEffect(() => {
    if (auth?.role !== "user" || auth.password_default) {
      return;
    }
    void refreshUserDashboard();
  }, [agentToken, auth?.role, auth?.password_default, userRangeDays]);

  useEffect(() => {
    if (!hasHydrated || auth?.role !== "admin" || auth.password_default) {
      return;
    }
    const nextPath = `/admin?tab=${encodeURIComponent(active)}`;
    if (window.location.pathname !== "/admin" || window.location.search !== `?tab=${active}`) {
      window.history.replaceState(null, "", nextPath);
    }
  }, [active, auth?.role, auth?.password_default, hasHydrated]);

  useEffect(() => {
    if (!hasHydrated || auth?.role !== "user" || auth.password_default) {
      return;
    }
    setUserView(userViewFromLocation());
    if (window.location.pathname.startsWith("/admin")) {
      window.history.replaceState(null, "", "/user/dashboard");
    }
  }, [auth?.role, auth?.password_default, hasHydrated]);

  useEffect(() => {
    if (!hasHydrated || auth?.role !== "admin" || auth.password_default) {
      return;
    }
    if (window.location.pathname.startsWith("/user")) {
      window.history.replaceState(null, "", `/admin?tab=${active}`);
    }
  }, [active, auth?.role, auth?.password_default, hasHydrated]);

  useEffect(() => {
    if (auth?.role !== "admin" || auth.password_default) {
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
  }, [agentToken, auth?.role, auth?.password_default]);

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
    const resolved = resolveManualClass(manualClass);
    if (!resolved) {
      setNotice("Nhãn chưa nằm trong taxonomy 45 class. Hãy chọn nhãn hợp lệ trước khi lưu ảnh.");
      return;
    }
    if (!manualFiles?.length) {
      setNotice("Chưa chọn ảnh để thêm vào dataset.");
      return;
    }
    const form = new FormData();
    Array.from(manualFiles).forEach((file) => form.append("files", file));
    form.append("cls_name", resolved.className);
    form.append("cls_id", String(resolved.classId));
    setBusy(true);
    try {
      const result = await fetchAgent<{ count: number; message: string }>("/api/dataset/manual", {
        method: "POST",
        body: form
      });
      setManualClass(resolved.className);
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

  async function uploadManualPhoneData() {
    const resolved = resolveManualClass(trainingManualClass);
    if (!resolved) {
      setNotice("Nhãn chưa nằm trong taxonomy 45 class. Hãy nhập nhãn hợp lệ trước khi chọn/lưu ảnh.");
      return;
    }
    if (!manualPhoneFiles?.length) {
      setNotice("Chưa chọn ảnh điện thoại/manual để thêm.");
      return;
    }
    const form = new FormData();
    Array.from(manualPhoneFiles).forEach((file) => form.append("files", file));
    form.append("cls_name", resolved.className);
    form.append("cls_id", String(resolved.classId));
    setBusy(true);
    try {
      const result = await fetchAgent<{ count: number; message: string }>("/api/dataset/manual-phone", {
        method: "POST",
        body: form
      });
      setTrainingManualClass(resolved.className);
      setManualPhoneFiles(null);
      setDatasetSource("manual_phone_import");
      setDatasetTrusted("untrusted");
      setDatasetOffset(0);
      setNotice(
        `Đã thêm ${result.count} ảnh cho ${resolved.className}. Ảnh đang chờ vẽ bbox và chỉ train sau khi bấm Duyệt bbox.`
      );
      await refreshActive("training");
      const latest = await fetchAgent<DatasetItemsResponse>("/api/dataset/items?limit=1&source=manual_phone_import");
      if (latest.rows[0]) {
        await openAnnotation(latest.rows[0].item_id);
      }
    } finally {
      setBusy(false);
    }
  }

  async function captureCameraSample() {
    const resolved = resolveManualClass(trainingManualClass);
    if (!resolved) {
      setNotice("Chưa chọn class để ghi frame camera");
      return;
    }
    setBusy(true);
    try {
      const result = await fetchAgent<{ count: number; message: string }>("/api/dataset/camera-sample", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cls_name: resolved.className,
          cls_id: resolved.classId,
          use_latest_detection_box: true
        })
      });
      setTrainingManualClass(resolved.className);
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

  async function learnThisObject() {
    setBusy(true);
    try {
      const result = await fetchAgent<UnknownLearnResponse>("/api/learn-now/unknown/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          manual_hint: unknownHint.trim(),
          approved_cls_name: manualClass.trim(),
          cls_id: manualClass.trim() ? classIdForName(manualClass.trim()) : -1
        })
      });
      setUnknownLearn(result);
      const suggestion = result.suggestions[0];
      if (!manualClass.trim() && suggestion?.canonical_class) {
        setManualClass(suggestion.canonical_class);
      }
      setNotice(result.message);
      setDatasetSource("manual_camera_capture");
      setDatasetTrusted("untrusted");
      setDatasetOffset(0);
      if (result.item) {
        setAnnotation({ item: result.item, boxes: result.boxes });
        setAnnotationBoxes(result.boxes);
      }
      await refreshActive("data");
    } finally {
      setBusy(false);
    }
  }

  async function startCaptureSession() {
    const resolved = resolveManualClass(trainingManualClass);
    if (!resolved) {
      setNotice("Chưa chọn class để bắt đầu phiên chụp");
      return;
    }
    setBusy(true);
    try {
      const result = await fetchAgent<CaptureSession>("/api/dataset/capture-session/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cls_name: resolved.className,
          cls_id: resolved.classId,
          target_count: 24,
          holdout_count: 6
        })
      });
      setTrainingManualClass(resolved.className);
      setCaptureSession(result);
      setNotice("Đã bắt đầu phiên chụp. Xoay hoặc đổi vị trí bút trước mỗi lần chụp.");
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
      await refreshActive("training");
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

  async function searchLicensedWeb() {
    const suggestionClass = unknownLearn?.suggestions?.[0]?.canonical_class ?? "";
    const className = canonicalClassForLabel(manualClass) || suggestionClass;
    if (!className) {
      setNotice("Chưa có class để tìm nguồn ảnh");
      return;
    }
    setBusy(true);
    try {
      const result = await fetchAgent<WebSourceDiscoveryResponse>("/api/dataset/web-discovery/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cls_name: className,
          query: webQuery.trim() || unknownHint.trim() || className,
          limit: 10
        })
      });
      setWebDiscovery(result);
      setNotice(result.message);
    } finally {
      setBusy(false);
    }
  }

  function useWebCandidate(index: number) {
    const candidate = webDiscovery?.candidates[index];
    if (!candidate) {
      return;
    }
    setManualClass(candidate.canonical_class);
    setManualImageUrl(candidate.image_url);
    setManualSourcePageUrl(candidate.source_page_url);
    setManualSourceType(candidate.source_type === "google_cse" ? "licensed_url" : candidate.source_type);
    setNotice("Đã điền URL/page. Cần xác minh license và tác giả trước khi import.");
  }

  async function importManualImageUrl() {
    const resolved = resolveManualClass(manualClass);
    const imageUrl = manualImageUrl.trim();
    if (!resolved || !imageUrl) {
      setNotice("Cần nhập class và URL ảnh");
      return;
    }
    setBusy(true);
    try {
      const result = await fetchAgent<{ count: number; message: string }>("/api/dataset/manual-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          urls: [imageUrl],
          cls_name: resolved.className,
          cls_id: resolved.classId,
          source_page_url: manualSourcePageUrl.trim(),
          source_license: manualSourceLicense.trim(),
          source_author: manualSourceAuthor.trim(),
          source_type: manualSourceType,
          generated: manualGenerated
        })
      });
      setManualClass(resolved.className);
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
      const label = action === "delete" ? "xóa" : "cách ly metadata";
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
        quarantine: "cách ly metadata",
        mark_trusted: "duyệt train",
        mark_untrusted: "loại khỏi train"
      };
      setNotice(`Đã ${actionText[action]} ${result.count} ảnh`);
      setSelectedPaths([]);
      await refreshActive(active);
    } finally {
      setBusy(false);
    }
  }

  function classIdForName(name: string) {
    const canonical = canonicalClassForLabel(name) || name.trim();
    const selected = classOptions.find((item) => item.name.trim().toLowerCase() === canonical.toLowerCase());
    if (selected) {
      return selected.id;
    }
    return -1;
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
      setNotice(`Đã lưu ${result.boxes.length} bbox, còn cần duyệt trước khi train`);
      await refreshActive(active);
    } finally {
      setBusy(false);
    }
  }

  async function approveAnnotation() {
    if (!annotation) {
      return;
    }
    if (!annotationBoxes.length) {
      setNotice("Cần ít nhất một bbox trước khi duyệt");
      return;
    }
    setBusy(true);
    try {
      const payload: DatasetReviewRequest = {
        action: "bbox_approved",
        reason: "bbox_checked_in_web_editor",
        boxes: annotationBoxes
      };
      const result = await fetchAgent<DatasetAnnotationResponse>(
        `/api/dataset/items/${encodeURIComponent(annotation.item.item_id)}/review`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }
      );
      setAnnotation(result);
      setAnnotationBoxes(result.boxes);
      setNotice(`Đã duyệt bbox cho ${result.item.item_id}`);
      await refreshActive(active);
    } finally {
      setBusy(false);
    }
  }

  async function refreshLearnNowReferences() {
    setBusy(true);
    try {
      const result = await fetchAgent<LearnNowStatus>(
        learnNowPath("/api/learn-now/refresh-references", trainingManualClass),
        { method: "POST" }
      );
      setLearnNow(result);
      setNotice("Đã làm mới nhận diện reference cho mẫu đã review.");
      await refreshActive("training");
    } finally {
      setBusy(false);
    }
  }

  async function startLearnNowMicroTrain(profile: "micro" | "strong" = "micro") {
    const resolved = resolveManualClass(trainingManualClass);
    if (!resolved) {
      setNotice("Chưa chọn class để train nhanh");
      return;
    }
    setBusy(true);
    try {
      const result = await fetchAgent<{ ok: boolean; message: string }>("/api/learn-now/micro-train/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cls_name: resolved.className, profile })
      });
      setTrainingManualClass(resolved.className);
      setNotice(result.message);
      await refreshActive("training");
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
      setNotice(result.uart_connected ? "UART đã reconnect và sẵn sàng" : result.warning || result.uart_message);
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
      setNotice(enabled ? "Đã bật Actuation Test Mode" : "Đã tắt Actuation Test Mode");
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

  if (!auth) {
    return (
      <AuthLoginPanel
        error={sessionMessage}
        password={loginPassword}
        pending={busy}
        sessionMessage={sessionMessage}
        showPassword={showLoginPassword}
        username={loginUsername}
        onPasswordChange={setLoginPassword}
        onShowPasswordChange={setShowLoginPassword}
        onSubmit={() => void loginToAgent()}
        onUsernameChange={setLoginUsername}
      />
    );
  }

  if (auth.password_default) {
    return (
      <PasswordChangePanel
        auth={auth}
        busy={busy}
        confirmPassword={passwordConfirm}
        currentPassword={passwordCurrent}
        error={passwordError}
        newPassword={passwordNew}
        onConfirmPasswordChange={setPasswordConfirm}
        onCurrentPasswordChange={setPasswordCurrent}
        onLogout={() => void logoutFromAgent()}
        onNewPasswordChange={setPasswordNew}
        onSubmit={() => void changePassword()}
      />
    );
  }

  if (auth.role === "user") {
    return (
      <UserDashboardPanel
        agentError={agentError}
        advisor={userAdvisor}
        advisorQuestion={userAdvisorQuestion}
        analytics={userAnalytics}
        auth={auth}
        binMap={userBinMap}
        busy={busy}
        chatBusy={chatBusy}
        chatAnswer={userChat}
        chatQuestion={userChatQuestion}
        device={userDevice}
        experience={userExperience}
        history={userHistoryRows}
        operationAlerts={userAlerts}
        operationSchedules={userSchedules}
        imageToken={agentToken}
        notice={notice}
        passwordConfirm={passwordConfirm}
        passwordCurrent={passwordCurrent}
        passwordError={passwordError}
        passwordNew={passwordNew}
        rangeDays={userRangeDays}
        report={userReport}
        chatbotEnabled={userChatbotEnabled}
        view={userView}
        onAdvisorQuestionChange={setUserAdvisorQuestion}
        onAdvisorRequest={() => void requestUserAdvisor()}
        onChangePassword={() => void changePassword()}
        onChatQuestionChange={setUserChatQuestion}
        onChatRequest={(value) => void requestUserChat(value)}
        onChatbotEnabledChange={updateUserChatbotEnabled}
        onCompleteCollection={(scheduleId, note) => void completeCollection(scheduleId, note)}
        onLogout={() => void logoutFromAgent()}
        onPasswordConfirmChange={setPasswordConfirm}
        onPasswordCurrentChange={setPasswordCurrent}
        onPasswordNewChange={setPasswordNew}
        onRangeChange={(value) => {
          setUserRangeDays(value);
          setUserAdvisor(null);
          setUserChat(null);
        }}
        onRefresh={() => void refreshUserDashboard()}
        onRefreshOperations={() => void refreshUserOperations()}
        onReportDeviceIssue={(payload) => void reportDeviceIssue(payload)}
        onViewChange={setUserView}
      />
    );
  }

  return (
    <div className={`app-shell ${isSidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <TrashSorterLogo />
          </div>
          <div>
            <strong>Trash Sorter Pro</strong>
            <span>EcoSort AI</span>
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
        <button
          className="sidebar-toggle"
          onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          title={isSidebarCollapsed ? "Mở rộng" : "Thu gọn"}
        >
          {isSidebarCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
        </button>
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
            <AccountControl auth={auth} busy={busy} onLogout={() => void logoutFromAgent()} />
            <TopbarStatusControls
              agentError={agentError}
              auth={auth}
              busy={busy}
              status={status}
              training={training}
              onCameraStart={() => void runAction("/api/camera/start")}
              onCameraStop={() => void runAction("/api/camera/stop")}
              onNavigate={setActive}
              onRefresh={() => void refreshActive(active)}
            />
            <button
              className="emergency-button"
              disabled={busy}
              onClick={() => void runAction("/api/camera/stop")}
              type="button"
            >
              <AlertTriangle size={17} />
              <span>Dừng hệ thống</span>
            </button>
            <button
              aria-label="Làm mới dữ liệu dashboard"
              className="icon-button"
              onClick={() => void refreshActive(active)}
              title="Làm mới"
              type="button"
            >
              <RefreshCcw size={18} />
              <span>Làm mới</span>
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
        {active === "roles" ? <AdminRolesPanel catalog={roleCatalog} /> : null}
        {active === "devices" ? (
          <AdminDevicesPanel
            busy={busy}
            devices={operationDevices}
            onSaveDevice={(payload) => void saveOperationDevice(payload)}
          />
        ) : null}
        {active === "bin-map" ? (
          <AdminBinMapPanel
            busy={busy}
            map={adminBinMap}
            schedules={adminSchedules}
            onCreateStation={(payload) => void createBinStation(payload)}
            onDeleteStation={(stationId) => void deleteBinStation(stationId)}
            onPatchStation={(stationId, payload) => void patchBinStation(stationId, payload)}
            onRefresh={() => void refreshAdminOperations()}
          />
        ) : null}
        {active === "alerts" ? (
          <AdminAlertsPanel
            alerts={adminAlerts}
            busy={busy}
            schedules={adminSchedules}
            onPatchAlert={(alertId, statusValue) => void patchOperationAlert(alertId, statusValue)}
          />
        ) : null}
        {active === "data" ? (
          <DataPanel
            annotation={annotation}
            annotationBoxes={annotationBoxes}
            busy={busy}
            classFilter={datasetClass}
            classOptions={classOptions}
            importSource={importSource}
            itemLimit={DATASET_LIMIT}
            itemOffset={datasetOffset}
            itemTotal={datasetTotal}
            items={datasetItems}
            imageToken={agentToken}
            manualClass={manualClass}
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
            onPage={(nextOffset) => setDatasetOffset(Math.max(0, nextOffset))}
            onRelabelItem={(imagePath) => void relabelDatasetItem(imagePath)}
            onApproveAnnotation={() => void approveAnnotation()}
            onSaveAnnotation={() => void saveAnnotation()}
            onSourceFilterChange={updateDatasetSource}
            onSync={() => void runAction("/api/dataset/sync")}
            onToggleAll={toggleAllVisible}
            onToggleSelected={toggleSelectedPath}
            onTrustedFilterChange={updateDatasetTrusted}
          />
        ) : null}
        {active === "training" ? (
          <ManualTrainingPanel
            busy={busy}
            captureSession={captureSession}
            classOptions={classOptions}
            commonWasteItems={commonWasteItems}
            learnNow={learnNow}
            manualClass={trainingManualClass}
            manualPhoneFileCount={manualPhoneFiles?.length ?? 0}
            training={training}
            onClassChange={setTrainingManualClass}
            onCaptureCameraSample={() => void captureCameraSample()}
            onCaptureSessionFrame={() => void captureSessionFrame()}
            onImportPhoneData={() => void uploadManualPhoneData()}
            onLearnNowRefresh={() => void refreshLearnNowReferences()}
            onLearnNowTrain={(profile) => void startLearnNowMicroTrain(profile)}
            onManualPhoneFiles={setManualPhoneFiles}
            onStartCaptureSession={() => void startCaptureSession()}
            onStopCaptureSession={() => void stopCaptureSession()}
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
        {active === "settings" || active === "model" || active === "audio" ? (
          <SettingsPanel
            actuationMode={actuationMode}
            busy={busy}
            config={config}
            hardwareDiagnostics={hardwareDiagnostics}
            hardwareProfile={hardwareProfile}
            hardwareTest={hardwareTest}
            status={status}
            voicePackStatus={voicePackStatus}
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
        {active === "accounts" ? (
          <AdminAccountsPanel
            accounts={accounts}
            busy={busy}
            chatAnswer={adminChat}
            chatQuestion={adminChatQuestion}
            createPassword={createPassword}
            createRole={createRole}
            createUsername={createUsername}
            knowledgeCatalog={knowledgeCatalog}
            knowledgeEvaluation={knowledgeEvaluation}
            resetPassword={resetPassword}
            selectedOwner={selectedOwner}
            onAskChat={(value) => void requestAdminChat(value)}
            onBackfillOwner={() => void backfillOwner()}
            onChatQuestionChange={setAdminChatQuestion}
            onCreateAccount={() => void createAccount()}
            onCreatePasswordChange={setCreatePassword}
            onCreateRoleChange={setCreateRole}
            onCreateUsernameChange={setCreateUsername}
            onEvaluateKnowledge={(question, role) => void evaluateKnowledge(question, role)}
            onPatchKnowledge={(entry, patch) => void patchKnowledge(entry, patch)}
            onRefresh={() => void Promise.all([refreshAccounts(), refreshKnowledge()])}
            onReloadKnowledge={() => void reloadKnowledge()}
            onResetPassword={(username) => void resetAccountPassword(username)}
            onResetPasswordChange={setResetPassword}
            onSelectedOwnerChange={setSelectedOwner}
            onToggleActive={(username, activeValue) => void toggleAccountActive(username, activeValue)}
            onUpsertKnowledge={(payload) => void upsertKnowledge(payload)}
          />
        ) : null}
        {active === "reports" ? (
          <AdminReportsPanel
            history={filteredHistory}
            sourceQuality={sourceQuality}
            summary={summary}
            token={agentToken}
          />
        ) : null}
        {active === "training" && annotation ? (
          <AnnotationEditor
            annotation={annotation}
            boxes={annotationBoxes}
            busy={busy}
            classOptions={classOptions}
            imageToken={agentToken}
            selectedClass={trainingManualClass}
            onBoxesChange={setAnnotationBoxes}
            onClassChange={setTrainingManualClass}
            onClose={() => setAnnotation(null)}
            onApprove={() => void approveAnnotation()}
            onSave={() => void saveAnnotation()}
          />
        ) : null}
        {active !== "accounts" ? (
          <RoleChatbotLauncher
            answer={adminChat}
            busy={chatBusy}
            label="Chatbot Admin"
            placeholder="Hỏi về trạng thái camera, AI model, UART, dataset hoặc vận hành hôm nay."
            question={adminChatQuestion}
            role="admin"
            statusText="Trợ lý AI chạy qua agent backend. Nếu chưa sẵn sàng, cấu hình khóa AI trong môi trường backend rồi khởi động lại agent."
            title="Trợ lý vận hành"
            onAsk={(value) => void requestAdminChat(value)}
            onQuestionChange={setAdminChatQuestion}
          />
        ) : null}
      </main>
    </div>
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

function cameraHealthDetail(status: RuntimeStatus | null) {
  if (!status) {
    return "";
  }
  const diagnostics = status.camera_diagnostics ?? {};
  const reason = diagnostics.reason ? String(diagnostics.reason) : status.camera.message;
  const mean = numericDiagnostic(diagnostics.mean_brightness);
  const nonBlack = numericDiagnostic(diagnostics.non_black_ratio);
  const metrics = [
    mean == null ? "" : `mean ${Math.round(mean)}`,
    nonBlack == null ? "" : `non-black ${Math.round(nonBlack * 100)}%`
  ].filter(Boolean);
  return [reason, ...metrics].filter(Boolean).join(" | ");
}

function numericDiagnostic(value: unknown) {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : null;
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

function userViewFromLocation(): UserView {
  if (typeof window === "undefined") {
    return "dashboard";
  }
  const segments = window.location.pathname.split("/").filter(Boolean);
  const segment = segments[segments.length - 1] ?? "dashboard";
  const views: UserView[] = [
    "dashboard",
    "ecopet",
    "advice",
    "history",
    "device",
    "map",
    "alerts",
    "schedule",
    "collect",
    "report-issue",
    "analytics",
    "reports",
    "notifications",
    "community",
    "leaderboard",
    "account"
  ];
  return views.includes(segment as UserView) ? (segment as UserView) : "dashboard";
}

function subtitleFor(tab: TabId) {
  if (tab === "bin-map") {
    return "Bản đồ Thủ Đức với 10 trạm seed, 30 ngăn và fallback list khi tile lỗi";
  }
  if (tab === "alerts") {
    return "Xem cảnh báo mở, cảnh báo thiết bị và lịch cần chú ý";
  }
  if (tab === "devices") {
    return "Quản lý thiết bị local, trạng thái và phụ trách";
  }
  if (tab === "roles") {
    return "Xem matrix quyền admin/user và scope vận hành local";
  }
  if (tab === "model") {
    return "Cấu hình model AI, ngưỡng và luồng đánh giá local";
  }
  if (tab === "audio") {
    return "Cấu hình audio, test MP3 và hành vi phát thanh";
  }
  if (tab === "reports") {
    return "Tổng hợp history, export CSV và chất lượng dataset cho Admin";
  }
  if (tab === "live") {
    return "Giám sát camera USB, AI detection và trạng thái UART theo thời gian thực";
  }
  if (tab === "history") {
    return "Tra cứu lịch sử nhận diện đã lưu trong history.db";
  }
  if (tab === "data") {
    return "Duyệt auto_low_conf, thêm data thủ công, vẽ bbox và giữ dataset sạch";
  }
  if (tab === "training") {
    return "Nhập nhãn trước, thêm ảnh điện thoại hoặc chụp camera, duyệt bbox rồi train candidate an toàn";
  }
  if (tab === "mapping") {
    return "Gán class sang lệnh UART và vị trí thùng phân loại";
  }
  if (tab === "settings") {
    return "Cấu hình model, camera USB-only, UART USB và capture queue";
  }
  if (tab === "accounts") {
    return "Quản lý tài khoản, force password change, backfill owner và chatbot vận hành";
  }
  return "Theo dõi log local agent và runtime";
}

function adminHistoryExportUrl(token: string) {
  const url = new URL(`${AGENT_URL}/api/history/export.csv`);
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

function localChatFailure(role: AuthRole, error: unknown): AiChatResponse {
  const detail = error instanceof Error ? sanitizeLocalChatError(error.message) : "";
  const base =
    role === "admin"
      ? "Trợ lý vận hành chưa trả lời được lúc này. Kiểm tra local agent hoặc thử lại sau vài giây."
      : "EcoPet chưa trả lời được lúc này. Bạn vẫn có thể xem biểu đồ, lịch sử rác và thử hỏi lại sau vài giây.";
  return {
    generated_at: new Date().toISOString(),
    available: false,
    provider: "local",
    model: "",
    answer_source: "local",
    latency_ms: 0,
    role,
    profile: role === "admin" ? "trash_sorter_admin" : "trash_sorter_user",
    message: detail ? `${base}\n• Chi tiết: ${detail}` : base,
    quick_prompts:
      role === "admin"
        ? ["Tóm tắt trạng thái local", "Kiểm tra camera", "Kiểm tra cấu hình trợ lý"]
        : ["Xem Eco Score", "Xem lịch sử rác", "Thử hỏi lại EcoPet"],
    knowledge_used: [],
    safety_notice: "Phản hồi local fallback, không gửi dữ liệu mới ra ngoài."
  };
}

function sanitizeLocalChatError(message: string) {
  return message
    .replace(/DEEPSEEK_[A-Z0-9_]+/gi, "[ẩn]")
    .replace(/sk-[A-Za-z0-9_-]+/g, "[ẩn]")
    .replace(/\.env(?:\.local)?/gi, "[ẩn]")
    .replace(/postgres(?:ql)?:\/\/\S+/gi, "[ẩn]")
    .replace(/[A-Za-z]:\\[^\s]+/g, "[ẩn]")
    .slice(0, 180)
    .trim();
}

function labelSource(source: string) {
  if (source === "roboflow") {
    return "Roboflow";
  }
  if (source === "manual_import") {
    return "Thủ công";
  }
  if (source === "manual_phone_import") {
    return "Ảnh điện thoại";
  }
  if (source === "manual_camera_capture") {
    return "Camera thủ công";
  }
  if (source === "manual_web_import") {
    return "Ảnh URL";
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

function datasetTrustLabel(item: DatasetItem) {
  const state = item.trust_state || (item.trusted ? "trainable" : "needs_review");
  if (state === "trainable") {
    return "Trainable";
  }
  if (state === "needs_review") {
    return item.bbox_reviewed ? "Cần duyệt" : "Cần duyệt bbox";
  }
  if (state === "quarantine") {
    return "Cách ly";
  }
  if (state === "hard_negative") {
    return "Mẫu âm";
  }
  if (state === "holdout") {
    return "Holdout";
  }
  if (state === "excluded") {
    return "Không train";
  }
  return item.trusted ? "Trainable" : "Cần duyệt";
}

function datasetTrustDetails(item: DatasetItem) {
  const details = [
    item.review_reason,
    item.quarantine_reason,
    ...(item.trust_reasons ?? [])
  ].filter(Boolean);
  return Array.from(new Set(details)).slice(0, 3).join(", ");
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
