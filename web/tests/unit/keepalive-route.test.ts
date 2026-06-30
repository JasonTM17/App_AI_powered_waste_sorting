import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  runCloudKeepalive: vi.fn()
}));

vi.mock("@/lib/server/keepalive", () => ({
  runCloudKeepalive: mocks.runCloudKeepalive
}));

import { GET } from "@/app/api/cron/keepalive/route";

function request(authorization?: string, extraHeaders: Record<string, string> = {}) {
  return new NextRequest("http://localhost/api/cron/keepalive", {
    headers: {
      ...(authorization ? { Authorization: authorization } : {}),
      "x-vercel-cron-schedule": "0 3 * * 1,4",
      ...extraHeaders
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
    expect(mocks.runCloudKeepalive).not.toHaveBeenCalled();
  });

  it("rejects a request with the wrong bearer secret", async () => {
    vi.stubEnv("CRON_SECRET", "expected-secret");
    expect((await GET(request("Bearer wrong-secret"))).status).toBe(401);
    expect(mocks.runCloudKeepalive).not.toHaveBeenCalled();
  });

  it("touches the configured databases for an authorized bearer request", async () => {
    vi.stubEnv("CRON_SECRET", "expected-secret");
    mocks.runCloudKeepalive.mockResolvedValue({
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

  it("accepts a Vercel Cron request without bearer auth", async () => {
    mocks.runCloudKeepalive.mockResolvedValue({
      configured: true,
      ok: true,
      targets: [{ name: "auth+supabase", ok: true, touched_at: "2026-06-30T03:00:00.000Z" }]
    });

    const response = await GET(request(undefined, { "user-agent": "vercel-cron/1.0" }));
    expect(response.status).toBe(200);
    expect(mocks.runCloudKeepalive).toHaveBeenCalledOnce();
  });

  it("rejects spoofed cron requests with the wrong schedule", async () => {
    expect(
      (
        await GET(
          request(undefined, {
            "user-agent": "vercel-cron/1.0",
            "x-vercel-cron-schedule": "*/5 * * * *"
          })
        )
      ).status
    ).toBe(503);
    expect(mocks.runCloudKeepalive).not.toHaveBeenCalled();
  });

  it("returns a failing status when a configured database cannot be touched", async () => {
    vi.stubEnv("CRON_SECRET", "expected-secret");
    mocks.runCloudKeepalive.mockResolvedValue({
      configured: true,
      ok: false,
      targets: [{ name: "supabase", ok: false }]
    });

    expect((await GET(request("Bearer expected-secret"))).status).toBe(503);
  });
});
