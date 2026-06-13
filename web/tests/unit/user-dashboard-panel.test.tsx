import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UserDashboardPanel } from "@/components/user-dashboard-panel";
import { renderWithProviders } from "../helpers/render-with-providers";
import type { UserDashboardPanelProps } from "@/components/user-dashboard/user-dashboard-types";

function setup(overrides?: Partial<UserDashboardPanelProps>) {
  window.history.replaceState(null, "", "/user/dashboard");
  const defaultProps: UserDashboardPanelProps = {
    agentError: "",
    advisor: null,
    advisorQuestion: "",
    analytics: {
      generated_at: "2025-01-01T00:00:00Z",
      range_days: 7 as const,
      total: 42,
      today_total: 3,
      seven_day_total: 20,
      thirty_day_total: 38,
      average_confidence: 0.88,
      eco_score: { score: 72, label: "Kha", recyclable_rate: 35, inorganic_rate: 40, organic_rate: 25, consistency_score: 65 },
      device_status: {
        device_id: "dev-1", device_name: "EcoSort", location: "Thu Duc", owner_username: "test-user",
        online: true, status: "online" as const, message: "OK", bins: []
      },
      advice: [],
      recent_classifications: [],
      comparison: { previous_total: 40, delta: 2, delta_percent: 5 },
      bins: [],
      route_totals: [
        { command: "O" as const, route_label: "Huu co", bin_index: 0, count: 15, percent: 35.7 },
        { command: "R" as const, route_label: "Tai che", bin_index: 1, count: 12, percent: 28.6 },
        { command: "I" as const, route_label: "Vo co", bin_index: 2, count: 15, percent: 35.7 }
      ],
      top_classes: [],
      daily: [],
      monthly: [],
      yesterday: { date: "2025-01-01", total: 3, top_classes: [], route_totals: [] },
      insights: [],
      advisor_available: false,
      advisor_model: ""
    },
    auth: {
      role: "user" as const,
      capabilities: ["view_dashboard"],
      auth_required: false,
      account_id: 1,
      username: "test-user",
      token_source: "session" as const,
      password_default: false
    },
    binMap: null,
    busy: false,
    chatBusy: false,
    chatAnswer: null,
    chatQuestion: "",
    device: null,
    experience: null,
    history: [],
    notice: "",
    operationAlerts: null,
    operationRefresh: {
      lastUpdatedAt: "2025-01-01T00:00:00Z",
      isRefreshing: false,
      refreshError: ""
    },
    operationSchedules: null,
    imageToken: "test-token",
    passwordConfirm: "",
    passwordCurrent: "",
    passwordError: "",
    passwordNew: "",
    rangeDays: 7,
    report: null,
    chatbotEnabled: false,
    view: "dashboard" as const,
    onAdvisorQuestionChange: vi.fn(),
    onAdvisorRequest: vi.fn(),
    onChangePassword: vi.fn(),
    onChatQuestionChange: vi.fn(),
    onChatRequest: vi.fn(),
    onChatbotEnabledChange: vi.fn(),
    onCompleteCollection: vi.fn(),
    onLogout: vi.fn(),
    onPasswordConfirmChange: vi.fn(),
    onPasswordCurrentChange: vi.fn(),
    onPasswordNewChange: vi.fn(),
    onRangeChange: vi.fn(),
    onRefresh: vi.fn(),
    onRefreshOperations: vi.fn(),
    onReportDeviceIssue: vi.fn(),
    onUserMapInteraction: vi.fn(),
    onViewChange: vi.fn(),
    ...overrides
  };
  const result = renderWithProviders(<UserDashboardPanel {...defaultProps} />);
  return { props: defaultProps, ...result };
}

describe("UserDashboardPanel", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders user nav items and calls onViewChange when clicked", async () => {
    const { props } = setup();
    const user = userEvent.setup();
    await user.click(screen.getByText("Lịch sử"));
    expect(props.onViewChange).toHaveBeenCalledWith("history");
  });

  it("renders range selector and calls onRangeChange on click", async () => {
    const { props } = setup();
    const user = userEvent.setup();
    await user.click(screen.getByText("30 ngày"));
    expect(props.onRangeChange).toHaveBeenCalledWith(30);
  });

  it("displays agent error banner when agentError is set", () => {
    setup({ agentError: "Không kết nối được local agent" });
    expect(screen.getByText(/không kết nối được local agent/i)).toBeInTheDocument();
  });

  it("renders the app shell with sidebar, topbar, and workspace", () => {
    setup();
    // "Trash Sorter Pro" appears in both sidebar (brand) and topbar (header title).
    expect(screen.getAllByText("Trash Sorter Pro").length).toBeGreaterThan(0);
    expect(screen.getByText("Xin chào, test-user")).toBeInTheDocument();
    expect(screen.getAllByText("Tổng quan").length).toBeGreaterThan(0);
  });

  it("persists collapsed sidebar preference", async () => {
    const user = userEvent.setup();
    const { container, unmount } = setup();

    await user.click(screen.getByRole("button", { name: /thu gọn thanh điều hướng/i }));
    expect(window.localStorage.getItem("trash-sorter-user-sidebar-collapsed")).toBe("1");
    expect(container.querySelector(".app-shell")).toHaveClass("sidebar-collapsed");

    unmount();
    setup();
    await waitFor(() => {
      expect(document.querySelector(".app-shell")).toHaveClass("sidebar-collapsed");
    });
  });

  it("renders EcoPet as an actionable user screen", async () => {
    const { props } = setup({ chatbotEnabled: false, view: "ecopet" });
    const user = userEvent.setup();

    expect(screen.getByText("Trợ lý thói quen xanh")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Eco Score/i }));

    expect(props.onChatQuestionChange).toHaveBeenCalledWith("Gợi ý một việc nhỏ để tăng Eco Score");
    expect(props.onChatRequest).toHaveBeenCalledWith("Gợi ý một việc nhỏ để tăng Eco Score");
  });

  it("keeps local Eco-Share posts after leaving the community screen", async () => {
    const user = userEvent.setup();
    const { unmount } = setup({ view: "community" });

    await user.type(screen.getByPlaceholderText(/Chia sẻ/i), "Mình vừa hoàn thành thử thách phân loại sạch.");
    await user.click(screen.getByRole("button", { name: /Đăng bài/i }));
    expect(screen.getAllByText(/Mình vừa hoàn thành thử thách/i).length).toBeGreaterThan(0);

    unmount();
    setup({ view: "community" });

    await waitFor(() => {
      expect(screen.getAllByText(/Mình vừa hoàn thành thử thách/i).length).toBeGreaterThan(0);
    });
  });
});
