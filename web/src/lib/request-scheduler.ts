export type RequestTaskContext = {
  attempt: number;
  signal: AbortSignal;
};

export type RetryDecision = {
  retry: boolean;
  retryAfterMs?: number;
};

export type ScheduleOptions<T> = {
  signal?: AbortSignal;
  timeoutMs?: number;
  maxRetries?: number;
  retryOn?: (outcome: { error?: unknown; value?: T }) => RetryDecision;
};

type QueueItem<T> = {
  task: (context: RequestTaskContext) => Promise<T>;
  options: ScheduleOptions<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
  onAbort?: () => void;
};

export class RequestTimeoutError extends Error {
  constructor(timeoutMs: number) {
    super(`Request timed out after ${timeoutMs}ms`);
    this.name = "RequestTimeoutError";
  }
}

export class RequestScheduler {
  private active = 0;
  private readonly queue: QueueItem<unknown>[] = [];

  constructor(
    readonly concurrency: number,
    private readonly random: () => number = Math.random
  ) {
    if (!Number.isInteger(concurrency) || concurrency < 1) {
      throw new Error("Request scheduler concurrency must be a positive integer");
    }
  }

  schedule<T>(
    task: (context: RequestTaskContext) => Promise<T>,
    options: ScheduleOptions<T> = {}
  ): Promise<T> {
    if (options.signal?.aborted) return Promise.reject(abortError());
    return new Promise<T>((resolve, reject) => {
      const item: QueueItem<T> = { task, options, resolve, reject };
      if (options.signal) {
        item.onAbort = () => {
          const index = this.queue.indexOf(item as QueueItem<unknown>);
          if (index >= 0) {
            this.queue.splice(index, 1);
            reject(abortError());
          }
        };
        options.signal.addEventListener("abort", item.onAbort, { once: true });
      }
      this.queue.push(item as QueueItem<unknown>);
      this.drain();
    });
  }

  private drain() {
    while (this.active < this.concurrency && this.queue.length) {
      const item = this.queue.shift();
      if (!item) return;
      if (item.onAbort && item.options.signal) {
        item.options.signal.removeEventListener("abort", item.onAbort);
      }
      this.active += 1;
      void this.run(item).finally(() => {
        this.active -= 1;
        this.drain();
      });
    }
  }

  private async run(item: QueueItem<unknown>) {
    try {
      const maxRetries = Math.max(0, item.options.maxRetries ?? 0);
      for (let attempt = 0; ; attempt += 1) {
        try {
          const value = await this.runAttempt(item, attempt);
          const decision = item.options.retryOn?.({ value }) ?? { retry: false };
          if (!decision.retry || attempt >= maxRetries) {
            item.resolve(value);
            return;
          }
          await waitForRetry(this.retryDelay(attempt, decision.retryAfterMs), item.options.signal);
        } catch (error) {
          if (item.options.signal?.aborted || isAbortError(error)) throw error;
          const decision = item.options.retryOn?.({ error }) ?? { retry: false };
          if (!decision.retry || attempt >= maxRetries) throw error;
          await waitForRetry(this.retryDelay(attempt, decision.retryAfterMs), item.options.signal);
        }
      }
    } catch (error) {
      item.reject(error);
    }
  }

  private async runAttempt(item: QueueItem<unknown>, attempt: number) {
    const controller = new AbortController();
    const externalSignal = item.options.signal;
    const onAbort = () => controller.abort();
    externalSignal?.addEventListener("abort", onAbort, { once: true });
    let timedOut = false;
    const timeoutMs = item.options.timeoutMs;
    const timer = timeoutMs
      ? globalThis.setTimeout(() => {
          timedOut = true;
          controller.abort();
        }, timeoutMs)
      : undefined;
    try {
      return await item.task({ attempt, signal: controller.signal });
    } catch (error) {
      if (timedOut) throw new RequestTimeoutError(timeoutMs ?? 0);
      throw error;
    } finally {
      if (timer !== undefined) globalThis.clearTimeout(timer);
      externalSignal?.removeEventListener("abort", onAbort);
    }
  }

  private retryDelay(attempt: number, retryAfterMs?: number) {
    if (retryAfterMs !== undefined) return Math.max(0, retryAfterMs);
    const base = Math.min(1000, 250 * 2 ** attempt);
    return Math.round(base * (0.8 + this.random() * 0.4));
  }
}

export function envConcurrency(raw: string | undefined, fallback: number) {
  const parsed = Number.parseInt(raw ?? "", 10);
  return Number.isInteger(parsed) && parsed > 0 ? Math.min(parsed, 16) : fallback;
}

function waitForRetry(ms: number, signal?: AbortSignal) {
  if (signal?.aborted) return Promise.reject(abortError());
  return new Promise<void>((resolve, reject) => {
    const finish = () => {
      signal?.removeEventListener("abort", cancel);
      resolve();
    };
    const cancel = () => {
      globalThis.clearTimeout(timer);
      reject(abortError());
    };
    const timer = globalThis.setTimeout(finish, ms);
    signal?.addEventListener("abort", cancel, { once: true });
  });
}

function abortError() {
  return new DOMException("Request aborted", "AbortError");
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}
