import type {
  AiChatResponse,
  AnalyticsRangeDays,
  AuthMe,
  AlertsResponse,
  BinMapResponse,
  CollectionSchedulesResponse,
  DeviceIssueCreatePayload,
  UserAdvisorResponse,
  UserAnalytics,
  UserDevice,
  UserExperience,
  UserHistoryItem,
  UserReport
} from "@/lib/agent";

export type UserView =
  | "dashboard"
  | "ecopet"
  | "advice"
  | "history"
  | "device"
  | "map"
  | "alerts"
  | "schedule"
  | "collect"
  | "report-issue"
  | "analytics"
  | "reports"
  | "notifications"
  | "community"
  | "leaderboard"
  | "account";

export type UserDashboardPanelProps = {
  agentError: string;
  advisor: UserAdvisorResponse | null;
  advisorQuestion: string;
  analytics: UserAnalytics | null;
  auth: AuthMe | null;
  binMap: BinMapResponse | null;
  busy: boolean;
  chatAnswer: AiChatResponse | null;
  chatQuestion: string;
  device: UserDevice | null;
  experience: UserExperience | null;
  history: UserHistoryItem[];
  notice: string;
  operationAlerts: AlertsResponse | null;
  operationSchedules: CollectionSchedulesResponse | null;
  imageToken: string;
  passwordConfirm: string;
  passwordCurrent: string;
  passwordError: string;
  passwordNew: string;
  rangeDays: AnalyticsRangeDays;
  report: UserReport | null;
  chatbotEnabled: boolean;
  view: UserView;
  onAdvisorQuestionChange: (value: string) => void;
  onAdvisorRequest: () => void;
  onChangePassword: () => void;
  onChatQuestionChange: (value: string) => void;
  onChatRequest: (value?: string) => void;
  onChatbotEnabledChange: (value: boolean) => void;
  onCompleteCollection: (scheduleId: string, note: string) => void;
  onLogout: () => void;
  onPasswordConfirmChange: (value: string) => void;
  onPasswordCurrentChange: (value: string) => void;
  onPasswordNewChange: (value: string) => void;
  onRangeChange: (value: AnalyticsRangeDays) => void;
  onRefresh: () => void;
  onRefreshOperations: () => void;
  onReportDeviceIssue: (payload: DeviceIssueCreatePayload) => void;
  onViewChange: (value: UserView) => void;
};
