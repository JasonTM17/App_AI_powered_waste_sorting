import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CloudAuthIdentity } from "@/lib/server/cloud-auth";
import { cloudSetDemoHardwareTarget } from "@/lib/server/cloud-operations";

const USER: CloudAuthIdentity = {
  account_id: 9,
  role: "user",
  username: "alice",
  display_name: "Alice",
  expires_at: "2026-07-01T00:00:00Z",
  password_default: false
};

describe("demo hardware target hot path", () => {
  const query = vi.fn();

  beforeEach(() => {
    vi.stubEnv("TRASH_SORTER_DEMO_HARDWARE_TARGET", "1");
    vi.stubEnv("TRASH_SORTER_AUTH_DATABASE_URL", "postgresql://test:test@localhost/test");
    query.mockReset();
    query
      .mockResolvedValueOnce({ rows: [{ assigned_owner_username: "alice", bin_id: "station-a-I", bin_index: 3 }] })
      .mockResolvedValueOnce({ rows: [{
        owner_username: "alice",
        station_id: "station-a",
        bin_id: "station-a-I",
        bin_index: 3,
        selected_by: "alice",
        selected_at: "2026-06-18T00:00:00Z",
        active: true
      }] });
    globalThis.trashSorterCloudOperationsPool = { query } as never;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    delete globalThis.trashSorterCloudOperationsPool;
  });

  it("uses two scoped queries and ignores a forged User owner", async () => {
    const result = await cloudSetDemoHardwareTarget(USER, {
      station_id: "station-a",
      bin_id: "station-a-I",
      bin_index: 3,
      owner_username: "bob"
    });

    expect(result).toMatchObject({ ok: true, target: { owner_username: "alice", bin_index: 3 } });
    expect(query).toHaveBeenCalledTimes(2);
    expect(query.mock.calls.map(([sql]) => String(sql)).join("\n")).not.toMatch(/create table|create index/i);
    expect(query.mock.calls[0][1]).toEqual(["station-a", 3, "station-a-I", "alice"]);
  });
});
