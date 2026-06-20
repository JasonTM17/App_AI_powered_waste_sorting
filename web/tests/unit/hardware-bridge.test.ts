import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const authMock = vi.hoisted(() => ({
  authenticateSession: vi.fn()
}));

vi.mock("@/lib/server/cloud-auth", () => ({
  authenticateSession: authMock.authenticateSession,
  extractBearerToken: (value: string | null) => (value ?? "").replace(/^Bearer\s+/i, ""),
  CloudAuthConfigError: class CloudAuthConfigError extends Error {}
}));

import { getAdminConnectionCardPresentation, hardwareBridgePath, isCloudDashboardApiPath } from "@/lib/agent";
import { proxyHardwareBridge } from "@/lib/server/hardware-bridge";

describe("hardware bridge proxy", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    authMock.authenticateSession.mockReset();
    process.env.TRASH_SORTER_HARDWARE_BRIDGE_URL = "https://hardware.example.com";
    process.env.TRASH_SORTER_HARDWARE_BRIDGE_SECRET = "bridge-secret";
  });

  it("maps agent paths under the admin hardware gateway", () => {
    expect(hardwareBridgePath("/api/camera/start")).toBe("/api/admin/hardware/camera/start");
    expect(hardwareBridgePath("/api/learn-now/status?cls_name=Pen")).toBe(
      "/api/admin/hardware/learn-now/status?cls_name=Pen"
    );
  });

  it("denies user sessions before forwarding to hardware", async () => {
    authMock.authenticateSession.mockResolvedValue({
      role: "user",
      username: "user",
      password_default: false
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const response = await proxyHardwareBridge(adminRequest("/api/admin/hardware/camera/start", "POST"), [
      "camera",
      "start"
    ]);

    expect(response.status).toBe(403);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("does not forward unknown hardware paths", async () => {
    authMock.authenticateSession.mockResolvedValue({
      role: "admin",
      username: "admin",
      password_default: false
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const response = await proxyHardwareBridge(adminRequest("/api/admin/hardware/logs", "GET"), ["logs"]);

    expect(response.status).toBe(404);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("forwards stream token requests with the server-only bridge secret", async () => {
    authMock.authenticateSession.mockResolvedValue({
      role: "admin",
      username: "admin",
      password_default: false
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ token: "stream-ticket", expires_at: "2026-06-18T00:00:00Z" }), {
        status: 200,
        headers: { "content-type": "application/json" }
      })
    );

    const response = await proxyHardwareBridge(adminRequest("/api/admin/hardware/camera/stream-token", "POST"), [
      "camera",
      "stream-token"
    ]);
    const payload = await response.json();
    const forwarded = fetchSpy.mock.calls[0]?.[1] as RequestInit;
    const headers = forwarded.headers as Headers;

    expect(response.status).toBe(200);
    expect(headers.get("X-Hardware-Bridge-Secret")).toBe("bridge-secret");
    expect(payload.stream_url).toBe("https://hardware.example.com/api/camera/stream?stream_token=stream-ticket");
    expect(payload.stream_url).not.toContain("bridge-secret");
  });

  it("forwards live AI snapshots used by the production camera", async () => {
    authMock.authenticateSession.mockResolvedValue({
      role: "admin",
      username: "admin",
      password_default: false
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ status: { camera: { running: true } }, detections: [{ cls_name: "Paper" }] })
    );

    const response = await proxyHardwareBridge(adminRequest("/api/admin/hardware/live", "GET"), ["live"]);
    const payload = await response.json();

    expect(response.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(payload.detections[0].cls_name).toBe("Paper");
  });
});

describe("Admin connection card", () => {
  it("never exposes the local agent URL when production uses the cloud bridge", () => {
    const presentation = getAdminConnectionCardPresentation(true, "idle", "local API unavailable");

    expect(presentation).toEqual({
      eyebrow: "Kết nối phần cứng",
      endpoint: "Vercel Hardware Bridge",
      statusText: "Sẵn sàng kết nối",
      offline: false
    });
    expect(presentation.endpoint).not.toContain("localhost");
  });

  it("reports the real cloud bridge health after a connection attempt", () => {
    expect(getAdminConnectionCardPresentation(true, "online").statusText).toBe("Bridge đang hoạt động");
    expect(getAdminConnectionCardPresentation(true, "offline")).toMatchObject({
      statusText: "Bridge chưa sẵn sàng",
      offline: true
    });
  });

  it("keeps the local endpoint visible during local development", () => {
    const presentation = getAdminConnectionCardPresentation(false, "idle");

    expect(presentation.eyebrow).toBe("Local Agent");
    expect(presentation.endpoint).toMatch(/^http:\/\/(localhost|127\.0\.0\.1):/);
  });
});

describe("dashboard cloud routing", () => {
  it("allows existing Admin cloud API routes while keeping local-only agent routes out of production", () => {
    expect(isCloudDashboardApiPath("/api/admin/devices")).toBe(true);
    expect(isCloudDashboardApiPath("/api/admin/bin-map/station-1")).toBe(true);
    expect(isCloudDashboardApiPath("/api/admin/alerts?include_resolved=false")).toBe(true);
    expect(isCloudDashboardApiPath("/api/admin/chat")).toBe(true);
    expect(isCloudDashboardApiPath("/api/user/dashboard-summary?range_days=30")).toBe(true);

    expect(isCloudDashboardApiPath("/api/status")).toBe(false);
    expect(isCloudDashboardApiPath("/api/settings")).toBe(false);
    expect(isCloudDashboardApiPath("/api/admin/accounts")).toBe(false);
    expect(isCloudDashboardApiPath("/api/admin/knowledge")).toBe(false);
  });
});

function adminRequest(path: string, method: string) {
  return new NextRequest(`https://trash-sorter.test${path}`, {
    method,
    headers: { Authorization: "Bearer admin-session" }
  });
}
