import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatPanel } from "@/components/chat/chat-panel";
import type { AiChatResponse } from "@/lib/agent";

const USER_CHAT_RESPONSE: AiChatResponse = {
  generated_at: "2026-06-11T12:00:00Z",
  available: false,
  provider: "local",
  model: "deepseek-v4-flash",
  answer_source: "local",
  latency_ms: 0,
  role: "user",
  profile: "trash_sorter_user",
  message: "EcoPet trả lời bằng gợi ý an toàn.",
  quick_prompts: [],
  knowledge_used: [],
  safety_notice: ""
};

describe("ChatPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("does not expose internal assistant mode or model badges in the User EcoPet dock", () => {
    render(
      <ChatPanel
        answer={USER_CHAT_RESPONSE}
        busy={false}
        label="EcoPet"
        onAsk={vi.fn()}
        onClose={vi.fn()}
        onQuestionChange={vi.fn()}
        persona="ecopet"
        placeholder="Hỏi EcoPet..."
        question=""
        statusText="EcoPet sẵn sàng."
        title="EcoPet"
        variant="dock"
      />
    );

    expect(screen.queryByText("Chế độ local an toàn")).not.toBeInTheDocument();
    expect(screen.queryByText("deepseek-v4-flash")).not.toBeInTheDocument();
  });
});
