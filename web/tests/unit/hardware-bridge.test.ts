import { describe, expect, it } from "vitest";

import { isAllowedHardwareBridgeRoute } from "@/lib/server/hardware-bridge";

describe("hardware bridge history allowlist", () => {
  it("allows USB device refresh through the hardware bridge", () => {
    expect(isAllowedHardwareBridgeRoute("/api/devices/refresh", "POST")).toBe(true);
    expect(isAllowedHardwareBridgeRoute("/api/devices/refresh", "GET")).toBe(false);
    expect(isAllowedHardwareBridgeRoute("/api/devices/refresh", "DELETE")).toBe(false);
  });

  it("allows Admin history reads, images and label reviews", () => {
    expect(isAllowedHardwareBridgeRoute("/api/history", "GET")).toBe(true);
    expect(isAllowedHardwareBridgeRoute("/api/history/774/image", "GET")).toBe(true);
    expect(isAllowedHardwareBridgeRoute("/api/history/774/label", "PATCH")).toBe(true);
  });

  it("rejects unsafe methods and malformed history ids", () => {
    expect(isAllowedHardwareBridgeRoute("/api/history", "DELETE")).toBe(false);
    expect(isAllowedHardwareBridgeRoute("/api/history/not-a-number/label", "PATCH")).toBe(false);
    expect(isAllowedHardwareBridgeRoute("/api/history/774/label", "POST")).toBe(false);
  });
});
