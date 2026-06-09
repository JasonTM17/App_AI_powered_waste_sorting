import type {
  AiChatResponse,
  AnalyticsRangeDays,
  AuthMe,
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
  busy: boolean;
  chatAnswer: AiChatResponse | null;
  chatQuestion: string;
  device: UserDevice | null;
  experience: UserExperience | null;
  history: UserHistoryItem[];
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
  onLogout: () => void;
  onPasswordConfirmChange: (value: string) => void;
  onPasswordCurrentChange: (value: string) => void;
  onPasswordNewChange: (value: string) => void;
  onRangeChange: (value: AnalyticsRangeDays) => void;
  onRefresh: () => void;
  onViewChange: (value: UserView) => void;
};
