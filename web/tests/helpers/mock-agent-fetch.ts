import { vi } from "vitest";

type MockAgentFetchOptions = {
  /** Map of endpoint path (e.g. "/api/auth/login") to the response data to return */
  responses: Record<string, unknown>;
  /** Default delay in ms before the mock resolves (0 = immediate) */
  delayMs?: number;
};

/**
 * Sets up a mock for the agentFetch module that returns canned responses
 * based on the endpoint path. Uses generic test values — never real credentials.
 */
export function mockAgentFetch(opts: MockAgentFetchOptions) {
  const { responses, delayMs = 0 } = opts;

  const mockFn = vi.fn(async (path: string) => {
    if (delayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
    const matched = responses[path];
    if (matched !== undefined) {
      if (matched instanceof Error) {
        throw matched;
      }
      return matched;
    }
    return { ok: true };
  });

  // Mock the module-level functions exported by @/lib/agent
  vi.mock("@/lib/agent", async () => {
    const actual = await vi.importActual<typeof import("@/lib/agent")>("@/lib/agent");
    return {
      ...actual,
      agentFetch: mockFn
    };
  });

  return mockFn;
}

/**
 * Default mock auth/me response using generic test values.
 */
export const DEFAULT_AUTH_ME = {
  role: "user" as const,
  capabilities: ["view_dashboard"],
  auth_required: false,
  account_id: 1,
  username: "test-user",
  token_source: "session" as const,
  password_default: false
};

/**
 * Default mock status response.
 */
export const DEFAULT_RUNTIME_STATUS = {
  camera: { connected: true, running: true, message: "Camera active" },
  uart: { connected: true, running: true, message: "UART connected" },
  model: { connected: true, running: true, message: "Model ready" },
  three_bin_classifier: { connected: true, running: true, message: "3-bin active" },
  fps: 30,
  latency_ms: 12,
  current_source: "/dev/video0",
  current_port: "COM3",
  usb_cameras: [{ name: "cam0" }],
  serial_ports: [{ name: "COM3" }]
};

/**
 * Default mock training status.
 */
export const DEFAULT_TRAINING_STATUS = {
  running: false,
  run_name: "",
  log_path: "",
  results_path: "",
  best_model_path: "",
  last_model_path: "",
  progress_percent: 0,
  message: ""
};

/**
 * Default mock bin map response.
 */
export const DEFAULT_BIN_MAP_RESPONSE = {
  generated_at: "2025-01-01T00:00:00Z",
  center: { latitude: 10.85, longitude: 106.75, zoom: 14 },
  stations: [
    {
      id: 1,
      station_id: "station-1",
      name: "Trạm test 1",
      area: "Thu Duc",
      address: "123 Test Street",
      latitude: 10.85,
      longitude: 106.75,
      coordinate_verified: true,
      status: "active" as const,
      active: true,
      owner_username: "test-user",
      device_id: "device-1",
      note: "",
      seed_source: "seed",
      alert_total: 0,
      open_alert_total: 0,
      bins: [
        {
          id: 1,
          bin_id: "bin-1",
          station_id: "station-1",
          command: "O" as const,
          bin_index: 0,
          label: "Huu co",
          fill_percent: 42,
          status: "normal" as const,
          active: true,
          updated_at: "2025-01-01T00:00:00Z"
        }
      ],
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z"
    }
  ],
  total: 1
};
