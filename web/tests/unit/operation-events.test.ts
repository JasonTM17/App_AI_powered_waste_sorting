import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CloudAuthIdentity } from "@/lib/server/cloud-auth";
import { cloudOperationEvents } from "@/lib/server/cloud-operations";

const USER: CloudAuthIdentity = {
  account_id: 7,
  role: "user",
  username: "nguyen-son",
  display_name: "Nguyễn Sơn",
  expires_at: "2026-07-01T00:00:00Z",
  password_default: false
};

const ADMIN: CloudAuthIdentity = {
  ...USER,
  role: "admin",
  username: "admin"
};

describe("operation realtime event cursor", () => {
  const query = vi.fn();

  beforeEach(() => {
    vi.stubEnv("TRASH_SORTER_AUTH_DATABASE_URL", "postgresql://test:test@localhost/test");
    query.mockReset();
    globalThis.trashSorterCloudOperationsPool = { query } as never;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    delete globalThis.trashSorterCloudOperationsPool;
  });

  it("establishes a user-scoped cursor and requests one safe initial refresh", async () => {
    query.mockResolvedValueOnce({ rows: [{ cursor: "42" }] });
    const result = await cloudOperationEvents(USER, 0);

    expect(result).toEqual({ cursor: 42, changed: true, events: [] });
    expect(query.mock.calls[0][1]).toEqual(["nguyen-son"]);
    expect(String(query.mock.calls[0][0])).toContain("assigned_owner_username");
  });

  it("returns new fullness events and advances the cursor", async () => {
    query.mockResolvedValueOnce({
      rows: [{
        id: "43",
        event_name: "bin_status_changed",
        topic: "project:operations",
        payload: { station_id: "station-a", fill_percent: 96 },
        created_at: "2026-06-20T12:00:00Z"
      }]
    });
    const result = await cloudOperationEvents(USER, 42);

    expect(result.changed).toBe(true);
    expect(result.cursor).toBe(43);
    expect(result.events[0]).toMatchObject({ event_name: "bin_status_changed" });
    expect(query.mock.calls[0][1]).toEqual([42, "nguyen-son"]);
  });

  it("lets Admin consume the unscoped operations event cursor", async () => {
    query.mockResolvedValueOnce({ rows: [{ cursor: "57" }] });

    const result = await cloudOperationEvents(ADMIN, 0);

    expect(result).toEqual({ cursor: 57, changed: true, events: [] });
    expect(query.mock.calls[0][1]).toEqual([""]);
  });
});
