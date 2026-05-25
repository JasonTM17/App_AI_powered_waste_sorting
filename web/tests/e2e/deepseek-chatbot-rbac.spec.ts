import { expect, test } from "@playwright/test";

import {
  agentFetch,
  collectConsoleErrors,
  expectNoConsoleErrors,
  loginViaAgent,
  openAppAs,
  assertNoHorizontalOverflow
} from "./helpers";

test("Stitch pet chatbot is draggable, opens as popup, and handles missing DeepSeek key", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await openAppAs(page, "user", "/user/dashboard");

  await expect(page.locator(".chatbot-fab-copy")).toHaveCount(0);
  const pet = page.getByRole("button", { name: /Mở trợ lý AI/i });
  await expect(pet).toBeVisible();
  const triggerBox = await pet.boundingBox();
  expect(triggerBox).not.toBeNull();
  expect(triggerBox!.width).toBeGreaterThanOrEqual(52);
  expect(triggerBox!.width).toBeLessThanOrEqual(60);

  const promptCloud = page.locator(".chatbot-prompt-cloud");
  await expect(promptCloud).toHaveCount(0);
  await pet.hover();
  await expect(promptCloud).toBeVisible({ timeout: 1_000 });
  const cloudBox = await promptCloud.boundingBox();
  expect(cloudBox).not.toBeNull();
  expect(cloudBox!.y).toBeLessThan(triggerBox!.y);
  expect(triggerBox!.y - (cloudBox!.y + cloudBox!.height)).toBeGreaterThanOrEqual(-2);
  expect(triggerBox!.y - (cloudBox!.y + cloudBox!.height)).toBeLessThanOrEqual(12);
  const triggerAnimation = await pet.evaluate((node) => {
    const petNode = node.querySelector(".chatbot-pet");
    const hopNode = node.querySelector(".chatbot-pet-hop");
    return {
      pet: petNode ? getComputedStyle(petNode).animationName : "",
      hop: hopNode ? getComputedStyle(hopNode).animationName : ""
    };
  });
  expect(`${triggerAnimation.pet} ${triggerAnimation.hop}`).toMatch(/chatbot-pet/);

  const before = await pet.boundingBox();
  expect(before).not.toBeNull();
  const viewport = page.viewportSize();
  const maxPetWidth = (viewport?.width ?? 1440) <= 760 ? 80 : 92;
  expect(before!.width).toBeLessThanOrEqual(maxPetWidth);
  await page.mouse.move(before!.x + before!.width / 2, before!.y + before!.height / 2);
  await page.mouse.down();
  await page.mouse.move(Math.max(30, before!.x - 90), Math.max(30, before!.y - 70), { steps: 8 });
  await page.mouse.up();
  const after = await pet.boundingBox();
  expect(after).not.toBeNull();
  expect(Math.abs(after!.x - before!.x) + Math.abs(after!.y - before!.y)).toBeGreaterThan(20);

  await pet.click();
  const dock = page.locator(".chat-panel-dock");
  await expect(dock).toBeVisible();
  await expect(page.locator(".chat-panel-dock[role='dialog']")).toBeVisible();
  await expect(dock.locator(".stitch-chat-header")).toContainText(/EcoPet/i);
  await expect(dock.locator(".stitch-chat-prompts button")).toHaveCount(3);
  await expect(page.getByRole("button", { name: /Mở trợ lý AI/i })).toHaveCount(0);
  await dock.locator("textarea.stitch-chat-input").fill("Giải thích Eco Score của tôi.");
  await dock.getByRole("button", { name: /Gửi câu hỏi cho AI/i }).click();
  await expect(dock.locator(".stitch-chat-bubble.user")).toContainText("Giải thích Eco Score của tôi.");
  await expect(dock.locator(".stitch-chat-bubble.assistant")).toContainText(
    /trợ lý AI|gợi ý có sẵn|trợ lý trực tuyến|chưa trả lời được/i
  );
  const assistantText = (await dock.locator(".stitch-chat-bubble.assistant").textContent()) ?? "";
  expect(assistantText).not.toContain("DEEPSEEK_API_KEY");
  expect(assistantText).not.toContain(".env.local");
  expect(assistantText).not.toContain("sk-");
  expect(assistantText.toLowerCase()).not.toContain("powershell");

  await page.keyboard.press("Escape");
  await expect(dock).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Mở trợ lý AI/i })).toBeVisible();

  await pet.hover();
  const reopenedCloud = page.locator(".chatbot-prompt-cloud");
  await expect(reopenedCloud).toBeVisible({ timeout: 1_000 });
  const cloudQuestion = (await reopenedCloud.textContent())?.trim() ?? "";
  expect(cloudQuestion.length).toBeGreaterThan(4);
  await reopenedCloud.click();
  await expect(dock).toBeVisible();
  await expect(dock.locator("textarea.stitch-chat-input")).toHaveValue(cloudQuestion);
  await page.mouse.click(10, 10);
  await expect(dock).toHaveCount(0);

  await assertNoHorizontalOverflow(page);
  expectNoConsoleErrors(consoleErrors);
});

test("Admin and User chatbot endpoints keep role boundaries", async () => {
  const admin = await loginViaAgent("admin");
  const user = await loginViaAgent("user");

  const adminChat = await agentFetch("/api/admin/chat", admin.token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "Tóm tắt camera và UART hôm nay" })
  });
  expect(adminChat.status).toBe(200);
  const adminPayload = await adminChat.json();
  expect(adminPayload.role).toBe("admin");
  expect(adminPayload.model).toBe("deepseek-v4-flash");
  expect(adminPayload.profile).toBe("trash_sorter_admin");

  const userChat = await agentFetch("/api/user/chat", user.token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "Hôm qua tôi bỏ gì?" })
  });
  expect(userChat.status).toBe(200);
  const userPayload = await userChat.json();
  expect(userPayload.role).toBe("user");
  expect(userPayload.model).toBe("deepseek-v4-flash");
  expect(userPayload.profile).toBe("trash_sorter_user");

  const forbidden = await agentFetch("/api/admin/chat", user.token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "Tôi có được xem admin không?" })
  });
  expect(forbidden.status).toBe(403);
});
