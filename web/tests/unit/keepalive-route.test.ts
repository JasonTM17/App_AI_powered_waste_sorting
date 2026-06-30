import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  runDatabaseKeepalive: vi.fn()
}));

vi.mock("@/lib/server/keepalive", () => ({
  runDatabaseKeepalive: mocks.runDatabaseKeepalive
}));

import { GET } from "@/app/api/cron/keepalive/route";

function request(authorization?: string) {
  return new NextRequest("http://localhost/api/cron/keepalive", {
    headers: {
      ...(authorization ? { Authorization: authorization } : {}),
      "x-vercel-cron-schedule": "0 3 * * 1,4"
    }
  });
}

describe("keepalive route", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  it("fails safely when CRON_SECRET is missing", async () => {
    expect((await GET(request())).status).toBe(503);
    expect(mocks.runDatabaseKeepalive).not.toHaveBeenCalled();
  });

  it("rejects a request with the wrong bearer secret", async () => {
    vi.stubEnv("CRON_SECRET", "expected-secret");
    expect((await GET(request("Bearer wrong-secret"))).status).toBe(401);
    expect(mocks.runDatabaseKeepalive).not.toHaveBeenCalled();
  });

  it("touches the configured databases for an authorized Vercel cron request", async () => {
    vi.stubEnv("CRON_SECRET", "expected-secret");
    mocks.runDatabaseKeepalive.mockResolvedValue({
      configured: true,
      ok: true,
      targets: [{ name: "auth+supabase", ok: true, touched_at: "2026-06-30T03:00:00.000Z" }]
    });

    const response = await GET(request("Bearer expected-secret"));
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      schedule: "0 3 * * 1,4",
      source: "vercel-cron"
    });
  });

  it("returns a failing status when a configured database cannot be touched", async () => {
    vi.stubEnv("CRON_SECRET", "expected-secret");
    mocks.runDatabaseKeepalive.mockResolvedValue({
      configured: true,
      ok: false,
      targets: [{ name: "supabase", ok: false }]
    });

    expect((await GET(request("Bearer expected-secret"))).status).toBe(503);
  });
});
