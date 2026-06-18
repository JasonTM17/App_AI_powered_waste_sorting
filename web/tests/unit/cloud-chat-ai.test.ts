import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { askCloudDeepSeek, keepGreetingAnswerFocused, needsAccentRepair, polishAnswer } from "@/lib/server/cloud-chat-ai";

describe("cloud DeepSeek client", () => {
  beforeEach(() => {
    vi.stubEnv("DEEPSEEK_API_KEY", "test-secret");
    vi.stubEnv("DEEPSEEK_TIMEOUT_SECONDS", "5");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("sends role-safe context and returns polished Vietnamese", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      choices: [{ message: { content: "**Mình ổn nhé.**\n- Hôm nay bạn muốn xem Eco Score không?" } }]
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const answer = await askCloudDeepSeek("user", "Xem Eco Score", { scope: "user_owned_cloud_data" });
    expect(answer).toBe("Mình ổn nhé.\n• Hôm nay bạn muốn xem Eco Score không?");
    const request = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(request.messages[0].content).toContain("tiếng Việt có dấu");
    expect(request.messages[1].content).toContain("user_owned_cloud_data");
  });

  it("repairs a long response that has no Vietnamese diacritics", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ choices: [{ message: { content: "Hom nay minh van on va san sang dong hanh cung ban trong viec phan loai rac nhe." } }] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ choices: [{ message: { content: "Hôm nay mình vẫn ổn và sẵn sàng đồng hành cùng bạn trong việc phân loại rác nhé." } }] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const answer = await askCloudDeepSeek("user", "Hôm nay bạn thế nào?", {});
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(answer).toContain("Hôm nay mình vẫn ổn");
  });

  it("rejects provider errors and empty content", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("rate limited", { status: 429 })));
    await expect(askCloudDeepSeek("user", "Xin chào", {})).rejects.toMatchObject({ status: 429 });

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ choices: [{ message: { content: "" } }] }), { status: 200 })));
    await expect(askCloudDeepSeek("user", "Xin chào", {})).rejects.toThrow("provider failed");
  });

  it("detects unaccented output and removes raw Markdown", () => {
    expect(needsAccentRepair("Day la mot cau tra loi rat dai nhung hoan toan khong co dau tieng Viet trong noi dung.")).toBe(true);
    expect(needsAccentRepair("Đây là câu trả lời tiếng Việt có dấu đầy đủ và dễ đọc cho người dùng.")).toBe(false);
    expect(polishAnswer("## Tiêu đề\n**Nội dung**\n- Bước một", "user")).toBe("Tiêu đề\nNội dung\n• Bước một");
  });

  it("keeps greeting answers focused instead of listing unrelated features", () => {
    const answer = keepGreetingAnswerFocused(
      "Hôm nay bạn thế nào?",
      "Chào bạn, mình vẫn ổn và sẵn sàng hỗ trợ bạn.\n1. Eco Score: chưa có dữ liệu.\n2. Lịch sử: chưa có dữ liệu."
    );
    expect(answer).toBe("Chào bạn, mình vẫn ổn và sẵn sàng hỗ trợ bạn.");
  });
});
