import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  query: vi.fn(),
  map: vi.fn(),
  alerts: vi.fn(),
  schedules: vi.fn()
}));

vi.mock("@/lib/server/cloud-auth", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/server/cloud-auth")>()),
  cloudAuthPool: () => ({ query: mocks.query })
}));
vi.mock("@/lib/server/cloud-operations", () => ({
  cloudBinMap: mocks.map,
  cloudAlerts: mocks.alerts,
  cloudSchedules: mocks.schedules
}));

import type { CloudAuthIdentity } from "@/lib/server/cloud-auth";
import { buildCloudChatContext, consumeCloudChatQuota } from "@/lib/server/cloud-chat-context";

const USER: CloudAuthIdentity = {
  account_id: 9,
  role: "user",
  username: "alice",
  display_name: "Alice",
  avatar_path: "",
  expires_at: "2026-07-01T00:00:00Z",
  password_default: false
};

describe("cloud chat context and quota", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.map.mockResolvedValue({ stations: [], total: 0 });
    mocks.alerts.mockResolvedValue({ alerts: [], total: 0 });
    mocks.schedules.mockResolvedValue({ schedules: [], total: 0 });
  });

  it("increments monthly quota atomically and allows the 36th consumed request", async () => {
    mocks.query.mockResolvedValueOnce({ rows: [{ used: 36 }] });
    const quota = await consumeCloudChatQuota(9);

    expect(quota).toMatchObject({ quota_used: 36, quota_remaining: 0, quota_exceeded: false });
    expect(mocks.query.mock.calls[0][0]).toContain("on conflict (account_id, period)");
    expect(mocks.query.mock.calls[0][0]).toContain("where chat_usage.used < $4");
  });

  it("blocks the next request when the atomic update returns no row", async () => {
    mocks.query
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [{ used: 36 }] });
    const quota = await consumeCloudChatQuota(9);

    expect(quota).toMatchObject({ quota_used: 36, quota_remaining: 0, quota_exceeded: true });
  });

  it("uses the username as the SQL scope for every User history query", async () => {
    mocks.query
      .mockResolvedValueOnce({ rows: [{ today_total: 1, thirty_day_total: 3 }] })
      .mockResolvedValueOnce({ rows: [{ cls_name: "Paper", count: 2 }] })
      .mockResolvedValueOnce({ rows: [{ id: "paper", title: "Phân loại giấy", keywords: ["giấy"], body: "Giấy sạch thuộc nhóm tái chế." }] });

    const result = await buildCloudChatContext(USER, "Giấy bỏ vào đâu?");

    expect(mocks.query.mock.calls[0][1]).toEqual(["alice"]);
    expect(mocks.query.mock.calls[1][1]).toEqual(["alice"]);
    expect(mocks.map).not.toHaveBeenCalled();
    expect(result.context.scope).toBe("user_owned_cloud_data");
    expect(result.knowledgeUsed).toEqual(["Phân loại giấy"]);
  });
});
