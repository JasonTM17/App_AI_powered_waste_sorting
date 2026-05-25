import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const agentFetchMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/agent", async () => {
  const actual = await vi.importActual<typeof import("@/lib/agent")>("@/lib/agent");
  return {
    ...actual,
    agentFetch: agentFetchMock
  };
});

vi.mock("@/components/dataset/annotation-editor", () => ({
  AnnotationEditor: ({ selectedClass }: { selectedClass: string }) => (
    <div data-testid="training-annotation-selected-class">{selectedClass}</div>
  )
}));

import { DashboardClient } from "@/components/dashboard-client";

const ADMIN_ME = {
  role: "admin",
  capabilities: ["dataset", "training"],
  auth_required: true,
  account_id: 1,
  username: "qa-admin",
  token_source: "session",
  session_expires_at: "2026-06-11T12:00:00Z",
  password_default: false
};

const STATUS = {
  camera: { connected: false, running: false, message: "" },
  uart: { connected: false, running: false, message: "" },
  model: { connected: true, running: true, message: "ready" },
  three_bin_classifier: { connected: false, running: false, message: "" },
  camera_diagnostics: {},
  fps: 0,
  latency_ms: 0,
  current_source: "",
  current_port: "",
  usb_cameras: [],
  serial_ports: []
};

const TRAINING = {
  running: false,
  run_name: "",
  log_path: "",
  results_path: "",
  best_model_path: "",
  last_model_path: "",
  progress_percent: 0,
  message: "idle"
};

const CLASS_RESPONSE = {
  classes: [
    { id: 18, name: "Paper" },
    { id: 37, name: "Textile" }
  ]
};

const COMMON_WASTE = {
  items: [
    { label: "vải", canonical_class: "Textile", class_id: 37, aliases: ["miếng vải"] },
    { label: "paper", canonical_class: "Paper", class_id: 18, aliases: [] }
  ]
};

const LEARN_NOW = {
  generated_at: "2026-06-11T12:00:00Z",
  selected: null,
  classes: [],
  route_counts: {},
  reviewed_total: 0,
  reference_total: 0
};

const CAPTURE_SESSION = {
  active: false,
  session_id: "",
  cls_name: "",
  cls_id: 0,
  target_count: 24,
  accepted_count: 0,
  training_count: 0,
  holdout_count: 0,
  holdout_accepted: 0,
  rejected_count: 0,
  last_message: ""
};

function responseFor(path: string) {
  if (path === "/api/me") {
    return ADMIN_ME;
  }
  if (path.startsWith("/api/status")) {
    return STATUS;
  }
  if (path === "/api/training/status") {
    return TRAINING;
  }
  if (path === "/api/model/classes") {
    return CLASS_RESPONSE;
  }
  if (path === "/api/common-waste/catalog") {
    return COMMON_WASTE;
  }
  if (path === "/api/dataset/capture-session") {
    return CAPTURE_SESSION;
  }
  if (path.startsWith("/api/learn-now/status")) {
    return LEARN_NOW;
  }
  if (path === "/api/dataset/manual-phone") {
    return { ok: true, count: 1, message: "Manual phone images imported" };
  }
  if (path === "/api/dataset/items?limit=1&source=manual_phone_import") {
    return {
      rows: [{ item_id: "manual_phone_1", image_path: "manual_phone_1.jpg" }],
      total: 1
    };
  }
  if (path === "/api/dataset/items/manual_phone_1") {
    return {
      item: {
        item_id: "manual_phone_1",
        image_path: "manual_phone_1.jpg",
        meta_path: "manual_phone_1.json",
        source: "manual_phone_import",
        cls_name: "Textile",
        cls_id: 37,
        width: 20,
        height: 20,
        reviewed: false,
        trusted: false,
        bbox_reviewed: false,
        trust_state: "needs_review",
        trust_reasons: []
      },
      boxes: []
    };
  }
  return { ok: true };
}

describe("DashboardClient training annotation", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    agentFetchMock.mockReset();
  });

  it("normalizes an authenticated admin at the root route to the admin tab route", async () => {
    window.history.replaceState(null, "", "/");
    window.localStorage.setItem("trash-sorter-session-token", "qa-token");
    agentFetchMock.mockImplementation(async (path: string) => responseFor(path));

    render(<DashboardClient />);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/admin");
      expect(window.location.search).toBe("?tab=live");
    });
  });

  it("opens the training annotation editor with the Training tab class", async () => {
    window.history.replaceState(null, "", "/admin?tab=training");
    window.localStorage.setItem("trash-sorter-session-token", "qa-token");
    agentFetchMock.mockImplementation(async (path: string) => responseFor(path));

    const { container } = render(<DashboardClient />);

    await waitFor(() => {
      expect(container.querySelector('input[list="manual-training-label-options"]')).not.toBeNull();
    });
    const labelInput = container.querySelector<HTMLInputElement>('input[list="manual-training-label-options"]');
    fireEvent.change(labelInput!, { target: { value: "Textile" } });

    const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]');
    expect(fileInput).not.toBeNull();
    await userEvent.upload(
      fileInput!,
      new File(["image"], "cloth.jpg", { type: "image/jpeg" })
    );

    await userEvent.click(screen.getByRole("button", { name: /phone/i }));

    await expect(screen.findByTestId("training-annotation-selected-class")).resolves.toHaveTextContent("Textile");
  });
});
