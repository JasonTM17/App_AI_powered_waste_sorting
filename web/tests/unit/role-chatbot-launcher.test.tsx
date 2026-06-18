import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RoleChatbotLauncher } from "@/components/chat/role-chatbot-launcher";

describe("RoleChatbotLauncher", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("clamps saved mobile pet position above the bottom taskbar", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 740 });
    window.localStorage.setItem("trash-sorter-chatbot-pet-position-user", JSON.stringify({ x: 340, y: 700 }));

    render(
      <RoleChatbotLauncher
        answer={null}
        busy={false}
        label="EcoPet"
        placeholder="Hỏi EcoPet..."
        question=""
        role="user"
        statusText="Sẵn sàng"
        title="EcoPet"
        onAsk={vi.fn()}
        onQuestionChange={vi.fn()}
      />
    );

    const trigger = screen.getByRole("button", { name: /Mở trợ lý AI/i });
    await waitFor(() => expect(trigger).toHaveStyle({ top: "574px" }));
  });
});
