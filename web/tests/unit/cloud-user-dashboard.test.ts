import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server/cloud-operations", () => ({
  cloudOperationsPool: vi.fn()
}));

import { buildAnalytics, cleanAnalyticsRange } from "@/lib/server/cloud-user-dashboard";
import type { DeviceStatus } from "@/lib/agent";

const offlineDevice: DeviceStatus = {
  device_id: "",
  device_name: "Chưa được gán thiết bị",
  location: "",
  owner_username: "nguyen-son",
  online: false,
  status: "offline",
  message: "Tài khoản chưa được gán thiết bị EcoSort.",
  bins: []
};

describe("cloud user dashboard aggregation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-18T08:00:00+07:00"));
  });

  it("normalizes unsupported analytics ranges", () => {
    expect(cleanAnalyticsRange("7")).toBe(7);
    expect(cleanAnalyticsRange("365")).toBe(30);
    expect(cleanAnalyticsRange(null)).toBe(30);
  });

  it("returns a completed empty dashboard instead of an endless loading state", () => {
    const result = buildAnalytics([], { ...offlineDevice }, [], 30);

    expect(result.total).toBe(0);
    expect(result.daily).toHaveLength(30);
    expect(result.daily.every((day) => day.total === 0)).toBe(true);
    expect(result.insights[0]?.kind).toBe("empty");
    expect(result.device_status.device_name).toBe("Chưa được gán thiết bị");
  });

  it("aggregates only the supplied owner's rows by route and period", () => {
    const rows = [
      historyRow(1, "2026-06-18T01:00:00Z", "Plastic bottle", "I", 3, 0.9),
      historyRow(2, "2026-06-17T01:00:00Z", "Organic", "O", 1, 0.8),
      historyRow(3, "2026-05-10T01:00:00Z", "Pen", "R", 2, 0.7)
    ];

    const result = buildAnalytics(rows as never, { ...offlineDevice }, [], 30);

    expect(result.total).toBe(2);
    expect(result.route_totals.find((item) => item.command === "I")?.count).toBe(1);
    expect(result.route_totals.find((item) => item.command === "O")?.count).toBe(1);
    expect(result.average_confidence).toBe(85);
    expect(result.recent_classifications[0]?.category).toBe("recyclable");
  });
});

function historyRow(id: number, ts: string, clsName: string, command: string, binIndex: number, confidence: number) {
  return {
    id, ts, cls_name: clsName, confidence, route_label: null, bin_index: binIndex,
    uart_command: command, ack_status: "ok", device_id: "eco-1", image_available: false
  };
}
