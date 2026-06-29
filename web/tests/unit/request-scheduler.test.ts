import { describe, expect, it, vi } from "vitest";

import {
  envConcurrency,
  RequestScheduler,
  RequestTimeoutError
} from "@/lib/request-scheduler";

describe("RequestScheduler", () => {
  it("runs FIFO tasks within the configured concurrency", async () => {
    const scheduler = new RequestScheduler(2);
    const releases: Array<() => void> = [];
    const started: number[] = [];
    let active = 0;
    let maxActive = 0;
    const jobs = [0, 1, 2, 3].map((id) =>
      scheduler.schedule(async () => {
        started.push(id);
        active += 1;
        maxActive = Math.max(maxActive, active);
        await new Promise<void>((resolve) => releases.push(resolve));
        active -= 1;
        return id;
      })
    );

    await vi.waitFor(() => expect(started).toEqual([0, 1]));
    releases.shift()?.();
    await vi.waitFor(() => expect(started).toEqual([0, 1, 2]));
    releases.splice(0).forEach((release) => release());
    await vi.waitFor(() => expect(started).toEqual([0, 1, 2, 3]));
    releases.splice(0).forEach((release) => release());

    await expect(Promise.all(jobs)).resolves.toEqual([0, 1, 2, 3]);
    expect(maxActive).toBe(2);
  });

  it("removes an aborted queued task", async () => {
    const scheduler = new RequestScheduler(1);
    let releaseFirst: () => void = () => undefined;
    const first = scheduler.schedule(
      () => new Promise<void>((resolve) => {
        releaseFirst = resolve;
      })
    );
    const controller = new AbortController();
    const queued = scheduler.schedule(async () => "never", { signal: controller.signal });

    controller.abort();
    releaseFirst();

    await first;
    await expect(queued).rejects.toMatchObject({ name: "AbortError" });
  });

  it("retries transient failures with bounded attempts", async () => {
    vi.useFakeTimers();
    const scheduler = new RequestScheduler(1, () => 0.5);
    let attempts = 0;
    const result = scheduler.schedule(
      async () => {
        attempts += 1;
        if (attempts < 4) throw new Error("transient");
        return "ok";
      },
      {
        maxRetries: 3,
        retryOn: ({ error }) => ({ retry: Boolean(error) })
      }
    );

    await vi.runAllTimersAsync();

    await expect(result).resolves.toBe("ok");
    expect(attempts).toBe(4);
    vi.useRealTimers();
  });

  it("aborts an active task after its timeout", async () => {
    vi.useFakeTimers();
    const scheduler = new RequestScheduler(1);
    const result = scheduler.schedule(
      ({ signal }) =>
        new Promise<void>((_resolve, reject) => {
          signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
        }),
      { timeoutMs: 50 }
    );

    const assertion = expect(result).rejects.toBeInstanceOf(RequestTimeoutError);
    await vi.advanceTimersByTimeAsync(50);
    await assertion;
    vi.useRealTimers();
  });

  it("aborts while waiting to retry without starting another attempt", async () => {
    vi.useFakeTimers();
    const scheduler = new RequestScheduler(1, () => 0.5);
    const controller = new AbortController();
    let attempts = 0;
    const result = scheduler.schedule(
      async () => {
        attempts += 1;
        throw new Error("transient");
      },
      {
        signal: controller.signal,
        maxRetries: 3,
        retryOn: () => ({ retry: true })
      }
    );

    await vi.advanceTimersByTimeAsync(0);
    controller.abort();

    await expect(result).rejects.toMatchObject({ name: "AbortError" });
    expect(attempts).toBe(1);
    vi.useRealTimers();
  });

  it("normalizes environment concurrency", () => {
    expect(envConcurrency("2", 1)).toBe(2);
    expect(envConcurrency("0", 2)).toBe(2);
    expect(envConcurrency("999", 2)).toBe(16);
    expect(envConcurrency("invalid", 2)).toBe(2);
  });
});
