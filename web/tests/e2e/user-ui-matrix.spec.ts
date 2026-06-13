import { expect, test } from "@playwright/test";

import {
  AGENT_URL,
  assertChatbotDoesNotCover,
  assertNoHorizontalOverflow,
  assertNoTopbarOverlap,
  assertReadableFormControls,
  assertStitchPetLauncher,
  assertUserChartsRender,
  assertUserShellHasNoAdminControls,
  collectConsoleErrors,
  expectNoConsoleErrors,
  openAppAs,
  readQaState,
  userRoutes
} from "./helpers";

for (const route of userRoutes) {
  test(`User route ${route.path} renders cleanly`, async ({ page }) => {
    const consoleErrors = collectConsoleErrors(page);
    await openAppAs(page, "user", route.path);

    await expect(page.locator("body")).toContainText(route.expected);
    await assertUserShellHasNoAdminControls(page);
    await assertStitchPetLauncher(page, false);
    await assertReadableFormControls(page);
    await assertNoTopbarOverlap(page);
    if (route.path === "/user/dashboard") {
      await expect(page.locator("body")).toContainText(/Lượng rác hằng ngày|Phân loại gần đây/i);
    }
    if (route.path === "/user/ecopet") {
      await expect(page.locator("body")).toContainText(/Trợ lý thói quen xanh|Chat với EcoPet|EcoPet AI/i);
    }
    if (route.path !== "/user/ecopet") {
      await assertChatbotDoesNotCover(page, ".user-dashboard-grid");
    }
    await assertNoHorizontalOverflow(page);
    expectNoConsoleErrors(consoleErrors);
  });
}

test("range tabs update analytics charts without blank states", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await openAppAs(page, "user", "/user/analytics");

  for (const label of ["7 ngày", "30 ngày", "90 ngày", "180 ngày"]) {
    await page.getByRole("button", { name: label }).click();
    await expect(page.getByRole("button", { name: label })).toHaveAttribute("aria-pressed", "true");
    await assertUserChartsRender(page);
    await assertReadableFormControls(page);
    await assertNoHorizontalOverflow(page);
  }

  expectNoConsoleErrors(consoleErrors);
});

test("User navigation keeps URL, content, and browser history in sync", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await openAppAs(page, "user", "/user/dashboard");

  await page.getByRole("link", { name: /Lịch sử/i }).click();
  await expect(page).toHaveURL(/\/user\/history$/);
  await expect(page.locator("body")).toContainText(/Lịch sử của bạn|Plastic bottle|Aluminum can/i);

  await page.goBack();
  await expect(page).toHaveURL(/\/user\/dashboard$/);
  await expect(page.locator("body")).toContainText(/Lượng rác hằng ngày|Phân loại gần đây/i);

  await page.goForward();
  await expect(page).toHaveURL(/\/user\/history$/);
  await expect(page.locator("body")).toContainText(/Lịch sử của bạn|Plastic bottle|Aluminum can/i);
  await assertUserShellHasNoAdminControls(page);
  await assertNoHorizontalOverflow(page);

  expectNoConsoleErrors(consoleErrors);
});

test("User login preserves the requested direct User route", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const credentials = readQaState().accounts.user;
  await page.goto("/user/ecopet", { waitUntil: "domcontentloaded" });

  await page.locator('input[autocomplete="username"]').fill(credentials.username);
  await page.locator('input[autocomplete="current-password"]').fill(credentials.password);
  await page.getByRole("button", { name: /Đăng nhập/i }).click();

  await expect(page).toHaveURL(/\/user\/ecopet$/);
  await expect(page.locator(".ecopet-layout")).toBeVisible();
  await expect(page.locator("body")).toContainText(/Trợ lý thói quen xanh|Chat với EcoPet/i);
  await assertStitchPetLauncher(page, false);
  await assertNoHorizontalOverflow(page);

  expectNoConsoleErrors(consoleErrors);
});

test("EcoPet quick prompts are actionable inside the User app", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await page.route(`${AGENT_URL}/api/user/chat`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        generated_at: new Date().toISOString(),
        available: true,
        provider: "playwright",
        model: "mock-ecopet",
        answer_source: "test",
        latency_ms: 12,
        role: "user",
        profile: "trash_sorter_user",
        message: "EcoPet mock: tăng Eco Score bằng cách tách chai nhựa trước khi bỏ rác.",
        quick_prompts: ["Xem Eco Score", "Xem lịch sử rác"],
        knowledge_used: [],
        safety_notice: "",
        quota_remaining: 35,
        quota_limit: 36
      })
    });
  });
  await openAppAs(page, "user", "/user/ecopet");

  await expect(page.locator(".ecopet-layout")).toBeVisible();
  await expect(page.locator(".chat-panel-dock[role='dialog']")).toHaveCount(0);
  await page.getByRole("button", { name: /Eco Score/i }).first().click();
  await expect(page.locator(".ecopet-answer-card")).toContainText(/EcoPet mock|tăng Eco Score/i);
  await expect(page.getByLabel(/Câu hỏi cho EcoPet/i)).toHaveValue("");
  await assertNoHorizontalOverflow(page);

  expectNoConsoleErrors(consoleErrors);
});

test("User experience screens expose leaderboard, challenges, community, and notifications", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await openAppAs(page, "user", "/user/leaderboard");

  await expect(page.getByTestId("leaderboard-current-summary")).toBeVisible();
  await expect(page.locator(".leaderboard-row")).toHaveCount(3);
  await expect(page.getByTestId("leaderboard-current-row")).toHaveCount(1);
  await expect(page.locator(".challenge-row")).toHaveCount(3);
  await assertUserShellHasNoAdminControls(page);
  await assertNoHorizontalOverflow(page);

  await page.goto("/user/community", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".community-card")).not.toHaveCount(0);
  await expect(page.locator(".community-card").first()).toContainText(/Eco-Share local|Eco Score|luot/i);
  await page.getByPlaceholder(/Chia sẻ một thành tích/i).fill("Mình vừa hoàn thành thử thách phân loại sạch trong tuần này.");
  await page.getByRole("button", { name: /Đăng bài/i }).click();
  await expect(page.locator(".social-post-card").first()).toContainText(/Mình vừa hoàn thành thử thách/i);
  const firstLike = page.locator(".social-post-card").first().getByRole("button").first();
  await expect(firstLike).toContainText("0");
  await firstLike.click();
  await expect(firstLike).toContainText("1");
  const firstShare = page.locator(".social-post-card").first().getByRole("button").nth(1);
  await firstShare.click();
  await expect(firstShare).toContainText("1");
  const firstComment = page.locator(".social-post-card").first().getByRole("button").nth(2);
  await firstComment.click();
  await expect(firstComment).toContainText("1");
  await assertUserShellHasNoAdminControls(page);
  await assertNoHorizontalOverflow(page);

  await page.goto("/user/notifications", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".notification-center")).toBeVisible();
  await expect(page.locator(".notification-center .experience-card, .notification-center .empty-state")).not.toHaveCount(0);
  await assertUserShellHasNoAdminControls(page);
  await assertNoHorizontalOverflow(page);

  expectNoConsoleErrors(consoleErrors);
});

test("User history and safe report export stay scoped to the current account", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const session = await openAppAs(page, "user", "/user/history");

  await expect(page.locator("body")).toContainText(/Plastic bottle|Aluminum can|Banana peel/i);
  await expect(page.locator("body")).not.toContainText(/Electronics|Cigarette/i);

  const csvRes = await fetch(`${AGENT_URL}/api/user/history/export.csv?range_days=180`, {
    headers: { Authorization: `Bearer ${session.token}` }
  });
  expect(csvRes.status).toBe(200);
  const csv = await csvRes.text();
  expect(csv).toContain("Plastic bottle");
  expect(csv).not.toMatch(/image_path|annotated_path|meta_path|Electronics|Cigarette/);

  await assertNoHorizontalOverflow(page);
  expectNoConsoleErrors(consoleErrors);
});

test("User can hide and show the EcoPet chatbot from account settings", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await openAppAs(page, "user", "/user/account");

  const chatbotToggle = page.getByLabel(/Trợ lý EcoPet/i);
  await expect(page.getByRole("button", { name: /Mở trợ lý AI/i })).toBeVisible();
  await chatbotToggle.uncheck();
  await expect(page.getByRole("button", { name: /Mở trợ lý AI/i })).toHaveCount(0);
  await chatbotToggle.check();
  await expect(page.getByRole("button", { name: /Mở trợ lý AI/i })).toBeVisible();

  await assertNoHorizontalOverflow(page);
  expectNoConsoleErrors(consoleErrors);
});
