import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TopbarStatusControls } from "@/components/topbar-status-controls";
import { renderWithProviders } from "../helpers/render-with-providers";
import type { AuthMe, RuntimeStatus, TrainingStatus } from "@/lib/agent";

const ADMIN_AUTH: AuthMe = {
  role: "admin",
  capabilities: ["admin"],
  auth_required: false,
  account_id: 1,
  username: "test-admin",
  token_source: "session",
  session_expires_at: new Date(Date.now() + 3600000).toISOString(),
  password_default: false
};

const DEFAULT_STATUS: RuntimeStatus = {
  camera: { connected: true, running: true, message: "Camera active" },
  uart: { connected: true, running: true, message: "UART connected" },
  model: { connected: true, running: true, message: "Model ready" },
  three_bin_classifier: { connected: true, running: true, message: "3-bin active" },
  fps: 30,
  latency_ms: 12,
  current_source: "/dev/video0",
  current_port: "COM3",
  usb_cameras: [],
  serial_ports: []
};

const DEFAULT_TRAINING: TrainingStatus = {
  running: false,
  run_name: "",
  log_path: "",
  results_path: "",
  best_model_path: "",
  last_model_path: "",
  progress_percent: 0,
  message: ""
};

function setup(overrides?: {
  agentError?: string;
  auth?: AuthMe | null;
  busy?: boolean;
  status?: RuntimeStatus | null;
  training?: TrainingStatus | null;
  onCameraStart?: () => void;
  onCameraStop?: () => void;
  onNavigate?: (tab: string) => void;
  onRefresh?: () => void;
}) {
  const props = {
    agentError: "",
    auth: ADMIN_AUTH,
    busy: false,
    status: DEFAULT_STATUS,
    training: DEFAULT_TRAINING,
    onCameraStart: vi.fn(),
    onCameraStop: vi.fn(),
    onNavigate: vi.fn(),
    onRefresh: vi.fn(),
    ...overrides
  };
  const result = renderWithProviders(<TopbarStatusControls {...props} />);
  return { props, ...result };
}

describe("TopbarStatusControls", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it("shows agent online status when no agent error", () => {
    setup({ agentError: "" });
    const agentButton = screen.getByRole("button", { name: /xem trạng thái local agent/i });
    expect(agentButton.className).toContain("online");
  });

  it("shows agent offline in popover when agentError is set", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    setup({ agentError: "Agent not reachable" });
    await user.click(screen.getByRole("button", { name: /xem trạng thái local agent/i }));
    await waitFor(() => {
      expect(screen.getByText("Offline")).toBeInTheDocument();
    });
  });

  it("auto-closes popover on Escape key", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    setup();
    await user.click(screen.getByRole("button", { name: /xem trạng thái local agent/i }));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("shows session expiry time in agent popover", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    setup();
    await user.click(screen.getByRole("button", { name: /xem trạng thái local agent/i }));
    await waitFor(() => {
      expect(screen.getByText(/hết hạn \d{2}:\d{2}/i)).toBeInTheDocument();
    });
  });

  it("displays error message in agent popover when agentError is set", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    setup({ agentError: "Connection refused" });
    await user.click(screen.getByRole("button", { name: /xem trạng thái local agent/i }));
    await waitFor(() => {
      expect(screen.getByText(/connection refused/i)).toBeInTheDocument();
    });
  });

  it("formats custom error messages from the agent", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    setup({ agentError: "khong gui xuong phan cung" });
    await user.click(screen.getByRole("button", { name: /xem trạng thái local agent/i }));
    await waitFor(() => {
      expect(screen.getByText(/không gửi xuống phần cứng/i)).toBeInTheDocument();
    });
  });
});
