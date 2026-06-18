import { afterEach, describe, expect, it, vi } from "vitest";

import { streamCloudChat } from "@/lib/cloud-chat-stream";

describe("cloud chat SSE client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("emits progressive text and returns the final response", async () => {
    const done = {
      generated_at: "2026-06-18T00:00:00Z",
      available: true,
      provider: "deepseek",
      model: "deepseek-v4-flash",
      answer_source: "deepseek",
      latency_ms: 120,
      role: "user",
      profile: "trash_sorter_user",
      message: "Xin chào bạn",
      quick_prompts: [],
      knowledge_used: [],
      safety_notice: "safe"
    };
    const sse = [
      'event: meta\ndata: {"quota_remaining":35}\n\n',
      'event: delta\ndata: {"text":"Xin chào"}\n\n',
      'event: delta\ndata: {"text":" bạn"}\n\n',
      `event: done\ndata: ${JSON.stringify(done)}\n\n`
    ].join("");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(sse, {
      headers: { "Content-Type": "text/event-stream" }
    })));
    const progress = vi.fn();

    const result = await streamCloudChat({
      message: "Xin chào",
      onProgress: progress,
      path: "/api/user/chat",
      role: "user",
      signal: new AbortController().signal,
      token: "session"
    });

    expect(progress).toHaveBeenCalledTimes(2);
    expect(progress.mock.calls[1][0]).toMatchObject({ message: "Xin chào bạn", quota_remaining: 35 });
    expect(result).toEqual(done);
  });

  it("does not expose an HTML error body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<!DOCTYPE html><h1>Internal secret</h1>", {
      status: 502,
      headers: { "Content-Type": "text/html" }
    })));

    await expect(streamCloudChat({
      message: "status",
      onProgress: vi.fn(),
      path: "/api/admin/chat",
      role: "admin",
      signal: new AbortController().signal,
      token: "session"
    })).rejects.not.toThrow(/Internal secret/);
  });

  it("keeps local FastAPI JSON chat compatible", async () => {
    const completed = {
      generated_at: "2026-06-18T00:00:00Z", available: true, provider: "local",
      model: "local", answer_source: "local", latency_ms: 5, role: "user",
      profile: "trash_sorter_user", message: "Phản hồi local", quick_prompts: [],
      knowledge_used: [], safety_notice: "safe"
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(completed), {
      headers: { "Content-Type": "application/json" }
    })));
    const progress = vi.fn();

    const result = await streamCloudChat({
      message: "Xin chào", onProgress: progress, path: "/api/user/chat", role: "user",
      signal: new AbortController().signal, token: "session"
    });

    expect(result).toEqual(completed);
    expect(progress).toHaveBeenCalledWith(completed);
  });
});
