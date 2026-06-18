import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const authMock = vi.hoisted(() => ({ authenticateSession: vi.fn() }));
const dashboardMock = vi.hoisted(() => ({ cloudUserAnalytics: vi.fn() }));

vi.mock("@/lib/server/cloud-auth", () => ({
  authenticateSession: authMock.authenticateSession,
  extractBearerToken: (value: string | null) => (value ?? "").replace(/^Bearer\s+/i, ""),
  CloudAuthConfigError: class CloudAuthConfigError extends Error {}
}));

vi.mock("@/lib/server/cloud-user-dashboard", () => ({
  cleanAnalyticsRange: () => 30,
  cloudUserAnalytics: dashboardMock.cloudUserAnalytics
}));

import { GET } from "@/app/api/user/analytics/route";

describe("cloud User routes", () => {
  beforeEach(() => {
    authMock.authenticateSession.mockReset();
    dashboardMock.cloudUserAnalytics.mockReset();
  });

  it("returns 401 without a valid session", async () => {
    authMock.authenticateSession.mockResolvedValue(null);
    const response = await GET(request());
    expect(response.status).toBe(401);
    expect(dashboardMock.cloudUserAnalytics).not.toHaveBeenCalled();
  });

  it("returns 403 for an Admin session on a User-only route", async () => {
    authMock.authenticateSession.mockResolvedValue({ role: "admin", username: "admin" });
    const response = await GET(request());
    expect(response.status).toBe(403);
    expect(dashboardMock.cloudUserAnalytics).not.toHaveBeenCalled();
  });

  it("derives owner scope from the authenticated User identity", async () => {
    const identity = { role: "user", username: "nguyen-son" };
    authMock.authenticateSession.mockResolvedValue(identity);
    dashboardMock.cloudUserAnalytics.mockResolvedValue({ total: 4 });
    const response = await GET(request("?range_days=30&owner_username=other-user"));

    expect(response.status).toBe(200);
    expect(dashboardMock.cloudUserAnalytics).toHaveBeenCalledWith(identity, 30);
    expect(await response.json()).toEqual({ total: 4 });
  });
});

function request(query = "") {
  return new NextRequest(`https://trash-sorter.test/api/user/analytics${query}`, {
    headers: { Authorization: "Bearer session" }
  });
}
