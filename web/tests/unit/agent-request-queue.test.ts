import { afterEach, describe, expect, it, vi } from "vitest";

import { agentFetch, AgentApiError } from "@/lib/agent";

describe("agent request queue", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("retries transient GET failures and returns the successful response", async () => {
    vi.useFakeTimers();
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        calls += 1;
        if (calls < 3) {
          return Response.json({ detail: "busy" }, { status: 503 });
        }
        return Response.json({ ready: true });
      })
    );

    const result = agentFetch<{ ready: boolean }>("/api/status", { timeoutMs: 5000 }, "");
    await vi.runAllTimersAsync();

    await expect(result).resolves.toEqual({ ready: true });
    expect(calls).toBe(3);
  });

  it("does not retry unsafe POST requests", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({ detail: "busy" }, { status: 503 })
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      agentFetch("/api/hardware/audio-test", { method: "POST" }, "")
    ).rejects.toBeInstanceOf(AgentApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
