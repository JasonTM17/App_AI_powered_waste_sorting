import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";

import { LivePanel } from "@/components/detection/live-panel";
import type { RuntimeStatus } from "@/lib/agent";
import { renderWithProviders } from "../helpers/render-with-providers";

const status: RuntimeStatus = {
  camera: { connected: true, running: false, message: "Camera off" },
  uart: { connected: false, running: false, message: "UART off" },
  model: { connected: true, running: true, message: "Model ready" },
  three_bin_classifier: { connected: true, running: false, message: "Kaggle fallback" },
  fps: 0,
  latency_ms: 0,
  current_source: "",
  current_port: "",
  usb_cameras: [],
  serial_ports: []
};

function renderPanel(nextStatus: RuntimeStatus) {
  return renderWithProviders(
    <LivePanel
      busy={false}
      detections={[]}
      status={nextStatus}
      stream=""
      training={null}
      onRefreshDevices={vi.fn()}
      onStart={vi.fn()}
      onStop={vi.fn()}
    />
  );
}

describe("LivePanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows a camera start action when the live camera is off", () => {
    renderPanel(status);

    expect(screen.getByRole("button", { name: /Bật camera/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Dừng camera/i })).not.toBeInTheDocument();
  });

  it("shows a camera stop action when the live camera is running", () => {
    renderPanel({ ...status, camera: { ...status.camera, running: true, message: "Camera active" } });

    expect(screen.getByRole("button", { name: /Dừng camera/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Bật camera/i })).not.toBeInTheDocument();
  });
});
