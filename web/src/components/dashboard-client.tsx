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
  Video,
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
  historyImageUrl,
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
  const refreshInFlightRef = useRef(false);

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
        })
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
        timeoutMs: 45_000
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
        timeoutMs: 45_000
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

  async function refreshActive(scope: TabId = active) {
    try {
      const settingsLike = scope === "settings" || scope === "model" || scope === "audio";
      const operationsLike = scope === "roles" || scope === "devices" || scope === "bin-map" || scope === "alerts";
      const dataLike = scope === "data";
      const trainingLike = scope === "training";
      const statusPath = settingsLike ? "/api/status" : "/api/status?include_devices=false";
      const [statusRes, trainingRes] = await Promise.all([
        fetchAgent<RuntimeStatus>(statusPath),
        fetchAgent<TrainingStatus>("/api/training/status")
      ]);
      setStatus(statusRes);
      setTraining(trainingRes);

      if (dataLike) {
        const [
          dataRes,
          itemRes,
          classesRes,
          commonWasteRes,
          captureSessionRes,
          learnNowRes,
          sourceQualityRes
        ] = await Promise.all([
          fetchAgent<DatasetSummary>("/api/dataset/summary"),
          fetchAgent<DatasetItemsResponse>(datasetItemsPath()),
          fetchAgent<ModelClassesResponse>("/api/model/classes"),
          fetchAgent<CommonWasteCatalogResponse>("/api/common-waste/catalog"),
          fetchAgent<CaptureSession>("/api/dataset/capture-session"),
          fetchAgent<LearnNowStatus>(learnNowPath()),
          fetchAgent<SourceQuality>("/api/dataset/source-quality")
        ]);
        setSummary(dataRes);
        setDatasetItems(itemRes.rows);
        setDatasetTotal(itemRes.total);
        setModelClasses(classesRes.classes);
        setCommonWasteItems(commonWasteRes.items);
        setCaptureSession(captureSessionRes);
        setLearnNow(learnNowRes);
        setSourceQuality(sourceQualityRes);
        setManualClass((current) => current || classesRes.classes[0]?.name || "");
        setSelectedPaths((current) =>
          current.filter((path) => itemRes.rows.some((item) => item.image_path === path))
        );
      }

      if (trainingLike) {
        const [classesRes, commonWasteRes, captureSessionRes, learnNowRes] = await Promise.all([
          fetchAgent<ModelClassesResponse>("/api/model/classes"),
          fetchAgent<CommonWasteCatalogResponse>("/api/common-waste/catalog"),
          fetchAgent<CaptureSession>("/api/dataset/capture-session"),
          fetchAgent<LearnNowStatus>(learnNowPath("/api/learn-now/status", trainingManualClass), { timeoutMs: 30_000 })
        ]);
        setModelClasses(classesRes.classes);
        setCommonWasteItems(commonWasteRes.items);
        setCaptureSession(captureSessionRes);
        setLearnNow(learnNowRes);
      }

      if (scope === "history") {
        const historyRes = await fetchAgent<HistoryResponse>("/api/history?limit=20");
        setHistory(historyRes.rows);
      }

      if (scope === "reports") {
        const [historyRes, dataRes, sourceQualityRes] = await Promise.all([
          fetchAgent<HistoryResponse>("/api/history?limit=20"),
          fetchAgent<DatasetSummary>("/api/dataset/summary"),
          fetchAgent<SourceQuality>("/api/dataset/source-quality")
        ]);
        setHistory(historyRes.rows);
        setSummary(dataRes);
        setSourceQuality(sourceQualityRes);
      }

      if (scope === "logs") {
        const logsRes = await fetchAgent<LogsResponse>("/api/logs?limit=120");
        setLogs(logsRes.lines);
      }

      if (settingsLike) {
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
        setVoicePackStatus(
          await fetchAgent<AudioVoicePackStatusResponse>(
            `/api/audio/voice-pack-status?gender=${encodeURIComponent(settingsRes.config.speaker.voice_gender ?? "female")}`
          )
        );
        setManualClass((current) => current || classesRes.classes[0]?.name || "");
      }

      if (scope === "mapping") {
        const mappingRes = await fetchAgent<MappingsResponse>("/api/mappings");
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
    const runRefresh = async () => {
      if (refreshInFlightRef.current || chatBusy || document.visibilityState === "hidden") {
        return;
      }
      refreshInFlightRef.current = true;
      try {
        await refreshActive(active);
      } finally {
        refreshInFlightRef.current = false;
      }
    };
    void runRefresh();
    const timer = window.setInterval(() => void runRefresh(), pollingIntervalMs);
    return () => window.clearInterval(timer);
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
    if (!hasHydrated || auth?.role !== "admin") {
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set("tab", active);
    window.history.replaceState(null, "", url.toString());
  }, [active, auth?.role, hasHydrated]);

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
    <div className="app-shell">
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
            selectedClass={manualClass}
            onBoxesChange={setAnnotationBoxes}
            onClassChange={setManualClass}
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

function AdminReportsPanel({
  history,
  sourceQuality,
  summary,
  token
}: {
  history: HistoryRow[];
  sourceQuality: SourceQuality | null;
  summary: DatasetSummary | null;
  token: string;
}) {
  const exportHref = adminHistoryExportUrl(token);
  const topClasses = Object.entries(summary?.classes ?? {})
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 8);
  const priorityIssues =
    sourceQuality?.classes
      .filter((item) => item.source_issue_count || item.missing_for_strong_train)
      .slice(0, 8) ?? [];
  return (
    <section className="content-grid admin-reports-grid">
      <div className="stat-row">
        <MetricCard label="Dòng lịch sử" value={formatNumber(history.length)} detail="Đang hiển thị gần đây" />
        <MetricCard label="Ảnh dataset" value={formatNumber(summary?.images ?? 0)} detail="Hàng đợi training" />
        <MetricCard label="Boxes" value={formatNumber(summary?.boxes ?? 0)} detail="BBox đã index" />
        <MetricCard
          label="Lỗi nguồn"
          value={formatNumber(sourceQuality?.invalid_source_images ?? 0)}
          detail="Nguồn cần kiểm tra"
        />
      </div>
      <div className="panel report-export-panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Báo cáo vận hành</span>
            <strong>Export lịch sử và chất lượng nguồn</strong>
          </div>
          <a className="primary-button" href={exportHref}>
            <Download size={17} />
            <span>Tải CSV Admin</span>
          </a>
        </div>
        <p className="muted-copy">
          CSV Admin giữ đủ trường vận hành hiện có để audit nội bộ. User export riêng chỉ trả
          các cột an toàn, không có path ảnh.
        </p>
      </div>
      <div className="panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Top class</span>
            <strong>Phân bố dataset</strong>
          </div>
        </div>
        <div className="class-list">
          {topClasses.length ? (
            topClasses.map(([name, count]) => (
              <div className="class-row" key={name}>
                <span>{name}</span>
                <strong>{formatNumber(Number(count))}</strong>
              </div>
            ))
          ) : (
            <div className="empty-state">Chưa có dataset summary.</div>
          )}
        </div>
      </div>
      <div className="panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Chất lượng nguồn</span>
            <strong>Class cần ưu tiên</strong>
          </div>
        </div>
        <div className="class-list">
          {priorityIssues.length ? (
            priorityIssues.map((item) => (
              <div className="class-row" key={item.class_name}>
                <span>
                  {item.class_name}
                  <small>{item.priority}</small>
                </span>
                <strong>{formatNumber(item.source_issue_count + item.missing_for_strong_train)}</strong>
              </div>
            ))
          ) : (
            <div className="empty-state">Chưa có cảnh báo source quality.</div>
          )}
        </div>
      </div>
      <HistoryPanel imageToken={token} rows={history.slice(0, 10)} />
    </section>
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
        <MetricCard
          label="Camera"
          value={status?.camera.running ? "ON" : "OFF"}
          detail={cameraHealthDetail(status)}
        />
        <MetricCard label="FPS" value={formatNumber(status?.fps ?? 0)} detail="Stream realtime" />
        <MetricCard label="Độ trễ" value={`${formatNumber(status?.latency_ms ?? 0)} ms`} detail="Nhận diện" />
        <MetricCard label="UART" value={status?.uart.connected ? "ON" : "OFF"} detail={status?.uart.message} />
        <MetricCard label="Training" value={trainEpoch} detail={trainDetail} />
        <MetricCard
          label="3-Bin"
          value={status?.three_bin_classifier.running ? "ON" : "OFF"}
          detail={status?.three_bin_classifier.message || "Kaggle fallback"}
        />
      </div>

      <div className="camera-panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Camera trực tiếp</span>
            <strong>{status?.current_source || "USB camera chưa chọn"}</strong>
          </div>
          <div className="button-row">
            <button className="secondary-button" disabled={busy} onClick={onRefreshDevices} type="button">
              <RefreshCcw size={17} />
              <span>Làm mới USB</span>
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
          {status?.camera.running && stream ? (
            <>
              <img className="camera-stream" src={stream} alt="USB camera stream" />
              <div className="scan-line" />
              <div className="vision-overlay">
                <ShieldCheck size={16} />
                <span>AI vision online</span>
              </div>
              <DetectionOverlay detections={detections} />
            </>
          ) : status?.camera.running ? (
            <div className="black-frame">
              <Camera size={42} />
              <span>Đang cấp quyền stream camera...</span>
            </div>
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
                    {item.route_label || "Chưa mapping"} {item.bin_index ? `- thùng ${item.bin_index}` : ""}
                  </small>
                  <small>
                    {item.serial_payload ? `Serial: ${item.serial_payload}` : "UART payload: -"}
                    {item.ack ? ` - ${item.ack}` : ""}
                  </small>
                  <small>Nguồn: {item.source || "YOLO"}</small>
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
          <span>{item.cls_name}{item.bin_index ? ` -> thùng ${item.bin_index}` : ""}</span>
          <small>{item.source || "YOLO"}</small>
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
  classFilter,
  classOptions,
  importSource,
  itemLimit,
  itemOffset,
  itemTotal,
  items,
  imageToken,
  manualClass,
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
  onPage,
  onRelabelItem,
  onApproveAnnotation,
  onSaveAnnotation,
  onSourceFilterChange,
  onSync,
  onToggleAll,
  onToggleSelected,
  onTrustedFilterChange
}: {
  annotation: DatasetAnnotationResponse | null;
  annotationBoxes: DatasetBox[];
  busy: boolean;
  classFilter: string;
  classOptions: ClassOption[];
  importSource: string;
  itemLimit: number;
  itemOffset: number;
  itemTotal: number;
  items: DatasetItem[];
  imageToken: string;
  manualClass: string;
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
  onPage: (offset: number) => void;
  onRelabelItem: (imagePath: string) => void;
  onApproveAnnotation: () => void;
  onSaveAnnotation: () => void;
  onSourceFilterChange: (value: string) => void;
  onSync: () => void;
  onToggleAll: (checked: boolean) => void;
  onToggleSelected: (path: string) => void;
  onTrustedFilterChange: (value: TrustedFilter) => void;
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
    "manual_phone_import",
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
        <div className="panel-toolbar no-pad">
          <div>
            <span className="eyebrow">Review dataset</span>
            <strong>Quản trị dữ liệu, không train trong tab này</strong>
          </div>
        </div>
        <p className="muted-copy">
          Thêm ảnh điện thoại, chụp camera, refresh reference và train candidate đã chuyển sang tab Huấn luyện để tránh lẫn với quản trị dataset.
        </p>
        <label className="source-name-field">
          Class thao tác
          <input
            list="data-action-class-options"
            maxLength={64}
            onChange={(event) => onClassChange(event.target.value)}
            placeholder="Chọn class để đổi nhãn hoặc duyệt bbox"
            value={manualClass}
          />
          <datalist id="data-action-class-options">
            {classOptions.map((item) => (
              <option key={`${item.id}-${item.name}-data-action`} value={item.name}>
                {item.name}
              </option>
            ))}
          </datalist>
        </label>
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
            <span>Duyệt train</span>
          </button>
          <button
            className="secondary-button compact-button"
            disabled={busy || !selectedPaths.length}
            onClick={() => onBulk("mark_untrusted")}
            type="button"
          >
            <AlertTriangle size={15} />
            <span>Loại train</span>
          </button>
          <button
            className="danger-button compact-button"
            disabled={busy || !selectedPaths.length}
            onClick={() => onBulk("quarantine")}
            type="button"
          >
            <AlertTriangle size={15} />
            <span>Cách ly meta</span>
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
                    <div className="trust-cell" title={datasetTrustDetails(item)}>
                      <StatusPill ok={item.trusted} text={datasetTrustLabel(item)} />
                      {datasetTrustDetails(item) ? <small>{datasetTrustDetails(item)}</small> : null}
                    </div>
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
          onApprove={onApproveAnnotation}
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
  onApprove,
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
  onApprove: () => void;
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
            <button className="primary-button" disabled={busy || !boxes.length} onClick={onApprove} type="button">
              <CheckCircle2 size={17} />
              <span>Duyệt bbox</span>
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
  voicePackStatus,
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
  voicePackStatus: AudioVoicePackStatusResponse | null;
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
        <span className="eyebrow">Kaggle 3-Bin Fallback</span>
        <div className="capture-warning">
          <BrainCircuit size={16} />
          <span>Chỉ dùng classifier này khi YOLO thấy Unknown trong ROI; không thay model YOLO production.</span>
        </div>
        <div className="form-grid two-col">
          <label className="check-field">
            <input
              checked={config.three_bin_classifier.enabled}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  three_bin_classifier: {
                    ...cfg.three_bin_classifier,
                    enabled: event.target.checked
                  }
                }))
              }
              type="checkbox"
            />
            Bật fallback 3 thùng
          </label>
          <label className="check-field">
            <input
              checked={config.three_bin_classifier.unknown_only}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  three_bin_classifier: {
                    ...cfg.three_bin_classifier,
                    unknown_only: event.target.checked
                  }
                }))
              }
              type="checkbox"
            />
            Chỉ sửa Unknown object
          </label>
          <label>
            Đường dẫn classifier
            <input
              value={config.three_bin_classifier.model_path}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  three_bin_classifier: {
                    ...cfg.three_bin_classifier,
                    model_path: event.target.value
                  }
                }))
              }
            />
          </label>
          <NumberField
            label="3-bin confidence"
            max={1}
            min={0}
            step={0.01}
            value={config.three_bin_classifier.min_confidence}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                three_bin_classifier: {
                  ...cfg.three_bin_classifier,
                  min_confidence: value
                }
              }))
            }
          />
          <NumberField
            label="3-bin margin"
            max={1}
            min={0}
            step={0.01}
            value={config.three_bin_classifier.min_margin}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                three_bin_classifier: {
                  ...cfg.three_bin_classifier,
                  min_margin: value
                }
              }))
            }
          />
          <NumberField
            label="Min crop area"
            max={1}
            min={0}
            step={0.001}
            value={config.three_bin_classifier.min_crop_area_ratio}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                three_bin_classifier: {
                  ...cfg.three_bin_classifier,
                  min_crop_area_ratio: value
                }
              }))
            }
          />
        </div>
        <div className="policy-strip">
          <ShieldCheck size={18} />
          <div>
            <strong>{status?.three_bin_classifier.running ? "Fallback đang bật" : "Fallback đang tắt"}</strong>
            <span>{status?.three_bin_classifier.message || "models/three_bin_classifier.pt"}</span>
          </div>
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
            <span>Làm mới USB</span>
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
            <span>UART OFF, không gửi xuống phần cứng. Cắm Arduino USB hoặc chọn đúng cổng rồi lưu.</span>
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
            Bật ROI vùng khay
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
            Bắt buộc ROI để đổ
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
          <NumberField
            label="Số class tối đa mỗi lần đổ"
            min={1}
            max={5}
            step={1}
            value={config.dispatch_guard.max_classes_per_dispatch}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                dispatch_guard: { ...cfg.dispatch_guard, max_classes_per_dispatch: Math.round(value) }
              }))
            }
          />
          <NumberField
            label="Cooldown cảnh báo nhiều rác (s)"
            min={0}
            max={120}
            step={1}
            value={config.dispatch_guard.multi_class_warning_cooldown_seconds}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                dispatch_guard: { ...cfg.dispatch_guard, multi_class_warning_cooldown_seconds: value }
              }))
            }
          />
          <NumberField
            label="Track loa cảnh báo"
            min={0}
            max={8}
            step={1}
            value={config.dispatch_guard.multi_class_warning_audio_track}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                dispatch_guard: { ...cfg.dispatch_guard, multi_class_warning_audio_track: Math.round(value) }
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
          <label>
            Phát bằng
            <select
              value={config.speaker.output_mode ?? (config.speaker.enabled ? "computer_speaker" : "hardware")}
              onChange={(event) => {
                const outputMode = event.target.value as "hardware" | "computer_speaker";
                onChange((cfg) => ({
                  ...cfg,
                  speaker: {
                    ...cfg.speaker,
                    output_mode: outputMode,
                    enabled: outputMode === "computer_speaker"
                  }
                }));
              }}
            >
              <option value="hardware">Phần cứng</option>
              <option value="computer_speaker">Loa máy tính</option>
            </select>
          </label>
          <label>
            Giọng loa máy tính
            <select
              value={config.speaker.voice_gender ?? "female"}
              onChange={(event) => {
                const voiceGender = event.target.value as "female" | "male";
                onChange((cfg) => ({
                  ...cfg,
                  speaker: {
                    ...cfg.speaker,
                    voice_gender: voiceGender
                  }
                }));
              }}
            >
              <option value="female">Giọng nữ</option>
              <option value="male">Giọng nam</option>
            </select>
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
        {voicePackStatus ? (
          <div className={voicePackStatus.missing_events.length ? "capture-warning" : "capture-note"}>
            <Wifi size={16} />
            <span>
              Voice pack {voicePackStatus.gender === "male" ? "giọng nam" : "giọng nữ"}:{" "}
              {voicePackStatus.available_count}/{voicePackStatus.total_count} event.
              {voicePackStatus.missing_events.length
                ? ` Thiếu: ${voicePackStatus.missing_events.join(", ")}.`
                : " Đủ file cho startup, phân loại, cảnh báo đầy thùng và cảnh báo nhiều vật."}
            </span>
          </div>
        ) : null}
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
    return <div className="empty-state">Đang tải mapping phần cứng...</div>;
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
        { label: "Home hiện tại", command: "I" as const, d6: Number(waitDegrees?.D6 ?? 90), d7: Number(waitDegrees?.D7 ?? 85) },
        { label: "Home D7 -2", command: "I" as const, d6: 90, d7: 83 },
        { label: "Home D7 +2", command: "I" as const, d6: 90, d7: 87 },
        { label: "Home D6 -2", command: "I" as const, d6: 88, d7: 85 },
        { label: "Home D6 +2", command: "I" as const, d6: 92, d7: 85 }
      ];
  const inorganicCandidates = Array.isArray(calibration.inorganic_replay_candidates)
    ? calibration.inorganic_replay_candidates.map(readAngleCandidate).filter((item) => item !== null)
    : [
        { label: "Vô cơ hiện tại", command: "R" as const, d6: 90, d7: 0 },
        { label: "Vô cơ trước đó", command: "R" as const, d6: 145, d7: 180 },
        { label: "Vô cơ max max", command: "R" as const, d6: 180, d7: 180 },
        { label: "Vô cơ D6 min", command: "R" as const, d6: 0, d7: 180 },
        { label: "Vô cơ D7 min", command: "R" as const, d6: 180, d7: 0 },
        { label: "Vô cơ cả hai min", command: "R" as const, d6: 0, d7: 0 },
        { label: "Vô cơ D6 45", command: "R" as const, d6: 45, d7: 180 },
        { label: "Vô cơ D7 45", command: "R" as const, d6: 180, d7: 45 }
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
    { label: "Hữu cơ sort", track: 2 },
    { label: "Vô cơ sort", track: 3 },
    { label: "Tái chế sort", track: 4 },
    { label: "Hữu cơ sensor", track: 5 },
    { label: "Tái chế sensor", track: 6 },
    { label: "Vô cơ sensor", track: 7 }
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
          <span className="eyebrow">Mapping phần cứng</span>
          <strong>{profile.profile_id || profile.current_port || "UART OFF"}</strong>
          <p className="muted">{profile.uart_message || "Chưa có trạng thái UART."}</p>
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
                Thùng {String(route.bin_index)} - servo {String(route.servo_pin)}
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
            <strong>Hiệu chuẩn home/upright</strong>
            <span>Replay offset nhỏ và chọn góc khi khay đứng thẳng, không bị nghiêng.</span>
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
            <strong>Replay hướng tái chế</strong>
            <span>Mỗi nút phát track 3, đổ theo góc thử, rồi trở về home hiện tại.</span>
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
            <strong>Hiệu chuẩn servo thô D6/D7</strong>
            <span>Chỉ dùng cặp góc thô để kiểm tra; thao tác này không phát audio phân loại.</span>
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
              <strong>Cảm biến âm thanh {String(sensor.label || sensor.command)}</strong>
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
              vô cơ D6={String((diagnostics.current_vo_co ?? diagnostics.current_inorganic).D6 ?? "-")},
              D7={String((diagnostics.current_vo_co ?? diagnostics.current_inorganic).D7 ?? "-")};
              tái chế D6={String(diagnostics.current_tai_che?.D6 ?? "-")},
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
            <span> - ACK OK chỉ xác nhận Arduino đã gửi lệnh MP3; nếu không nghe hãy kiểm tra microSD, file track, loa, nguồn, TX/RX D4-D5.</span>
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
          <strong>{enabled ? "Đang bật" : "Đang tắt"}</strong>
          <p className="muted">{"Kiem chung camera -> group -> bin -> payload -> ACK -> history."}</p>
        </div>
        <button
          className={enabled ? "danger-button" : "primary-button"}
          disabled={busy}
          onClick={() => onToggle(!enabled)}
          type="button"
        >
          {enabled ? <Square size={17} /> : <ShieldCheck size={17} />}
          <span>{enabled ? "Tắt test mode" : "Bật test mode"}</span>
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
        <div className="empty-state">Chưa có evidence. Bật camera live và đưa từng loại rác vào vùng nhận diện.</div>
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
