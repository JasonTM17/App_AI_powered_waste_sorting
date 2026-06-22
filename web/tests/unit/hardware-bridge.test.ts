import { describe, expect, it } from "vitest";

import { getAdminConnectionCardPresentation, shouldUseCloudHardwareBridge } from "@/lib/agent";
import { isAllowedHardwareBridgeRoute } from "@/lib/server/hardware-bridge";

describe("hardware bridge history allowlist", () => {
  it("uses the local agent by default unless the cloud bridge is explicitly enabled", () => {
    const originalVercel = process.env.NEXT_PUBLIC_VERCEL;
    process.env.NEXT_PUBLIC_VERCEL = undefined;
    expect(shouldUseCloudHardwareBridge()).toBe(false);
    expect(shouldUseCloudHardwareBridge("")).toBe(false);
    expect(shouldUseCloudHardwareBridge("0")).toBe(false);
    expect(shouldUseCloudHardwareBridge("false")).toBe(false);
    expect(shouldUseCloudHardwareBridge("1")).toBe(true);
    expect(shouldUseCloudHardwareBridge("true")).toBe(true);
    expect(shouldUseCloudHardwareBridge("cloud")).toBe(true);

    process.env.NEXT_PUBLIC_VERCEL = "1";
    expect(shouldUseCloudHardwareBridge()).toBe(false);
    expect(shouldUseCloudHardwareBridge("1")).toBe(true);
    expect(shouldUseCloudHardwareBridge("0")).toBe(false);

    process.env.NEXT_PUBLIC_VERCEL = originalVercel;
  });

  it("allows USB device refresh through the hardware bridge", () => {
    expect(isAllowedHardwareBridgeRoute("/api/devices/refresh", "POST")).toBe(true);
    expect(isAllowedHardwareBridgeRoute("/api/devices/refresh", "GET")).toBe(false);
    expect(isAllowedHardwareBridgeRoute("/api/devices/refresh", "DELETE")).toBe(false);
  });

  it("does not expose the local agent URL in the Admin sidebar card", () => {
    const card = getAdminConnectionCardPresentation(false, "idle", "");

    expect(card.endpoint).toBe("Máy phân loại cục bộ");
    expect(card.endpoint).not.toContain("http");
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
