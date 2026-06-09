import { expect, test } from "@playwright/test";

import {
  adminTabs,
  agentFetch,
  assertNoHorizontalOverflow,
  assertStitchPetLauncher,
  assertUserShellHasNoAdminControls,
  collectConsoleErrors,
  expectNoConsoleErrors,
  openAppAs,
  readQaState
} from "./helpers";

test("login screen renders Vietnamese production auth and admin can sign in", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const state = readQaState();

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Đăng nhập hệ thống/i })).toBeVisible();
  await page.getByLabel(/Tên đăng nhập/i).fill(state.accounts.admin.username);
  await page.getByLabel(/^Mật khẩu$/i).fill(state.accounts.admin.password);
  await page.getByRole("button", { name: /^Đăng nhập$/i }).click();

  await expect(page.getByRole("navigation", { name: /Main navigation/i })).toContainText(/Giám sát/i);
  await expect(page.locator(".page-heading h1")).toHaveText("Giám sát");
  await assertNoHorizontalOverflow(page);
  expectNoConsoleErrors(consoleErrors);
});

test("user session sees only User dashboard and is forbidden from Admin APIs", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const session = await openAppAs(page, "user", "/user/dashboard");

  await expect(page.locator("body")).toContainText(/Xin chào|Daily Waste Volume|Recent Classifications/i);
  await assertStitchPetLauncher(page, false);
  await assertUserShellHasNoAdminControls(page);

  const statusRes = await agentFetch("/api/status", session.token);
  expect(statusRes.status).toBe(403);
  const adminChatRes = await agentFetch("/api/admin/chat", session.token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "Tóm tắt vận hành" })
  });
  expect(adminChatRes.status).toBe(403);

  await assertNoHorizontalOverflow(page);
  expectNoConsoleErrors(consoleErrors);
});

test("admin tabs keep the existing operational surfaces reachable", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await openAppAs(page, "admin", "/admin?tab=live");

  for (const item of adminTabs) {
    await page.goto(`/admin?tab=${item.tab}`, { waitUntil: "networkidle" });
    await expect(page.locator(".page-heading h1")).toHaveText(item.title);
    await expect(page.getByRole("navigation", { name: /Main navigation/i })).toContainText(item.nav);
    await assertNoHorizontalOverflow(page);
  }

  expectNoConsoleErrors(consoleErrors);
});

test("topbar status icon controls open real Admin status popovers", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await openAppAs(page, "admin", "/admin?tab=live");

  const checks = [
    { button: /Camera USB/i, dialog: /Camera USB/i, detail: /Thiết bị USB|FPS|Nguồn/i },
    { button: /AI model/i, dialog: /AI model/i, detail: /Training|3-Bin fallback|Tiến độ/i },
    { button: /Local agent/i, dialog: /Local agent/i, detail: /URL|UART|Phiên/i }
  ];
  for (const item of checks) {
    await page.getByRole("button", { name: item.button }).click();
    const dialog = page.getByRole("dialog", { name: item.dialog });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(item.detail);
  }

  await assertNoHorizontalOverflow(page);
  expectNoConsoleErrors(consoleErrors);
});
