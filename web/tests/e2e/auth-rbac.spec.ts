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

  const stylesheets = await page.locator('link[rel="stylesheet"]').evaluateAll((links) =>
    links.map((link) => (link as HTMLLinkElement).href).filter(Boolean)
  );
  expect(stylesheets.length).toBeGreaterThan(0);
  const authStyles = await page.locator(".auth-panel").evaluate((panel) => {
    const screen = panel.closest(".auth-screen");
    const logo = panel.querySelector(".trash-sorter-logo-image");
    const panelStyle = window.getComputedStyle(panel);
    const screenStyle = screen ? window.getComputedStyle(screen) : null;
    const panelBox = panel.getBoundingClientRect();
    const logoBox = logo?.getBoundingClientRect();
    return {
      panelDisplay: panelStyle.display,
      panelMaxWidth: panelStyle.maxWidth,
      panelWidth: panelBox.width,
      screenDisplay: screenStyle?.display ?? "",
      logoHeight: logoBox?.height ?? 0,
      logoWidth: logoBox?.width ?? 0
    };
  });
  expect(authStyles.screenDisplay).toBe("grid");
  expect(authStyles.panelDisplay).toBe("grid");
  expect(authStyles.panelWidth).toBeLessThanOrEqual(460);
  expect(authStyles.logoWidth).toBeLessThanOrEqual(260);
  expect(authStyles.logoHeight).toBeLessThanOrEqual(160);

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

  await expect(page.locator("body")).toContainText(/Xin chào|Lượng rác hằng ngày|Phân loại gần đây/i);
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
    await page.goto(`/admin?tab=${item.tab}`, { waitUntil: "domcontentloaded" });
    await expect(page.locator(".page-heading h1")).toHaveText(item.title);
    await expect(page.getByRole("navigation", { name: /Main navigation/i })).toContainText(item.nav);
    await assertNoHorizontalOverflow(page);
  }

  expectNoConsoleErrors(consoleErrors);
});

test("training tab requires a canonical label before phone/manual upload", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await openAppAs(page, "admin", "/admin?tab=training");

  await expect(page.locator(".page-heading h1")).toHaveText("Huấn luyện");
  const labelInput = page.getByLabel(/^Nhãn$/i);
  const fileInput = page.locator('input[type="file"][accept="image/*"]').last();
  await labelInput.fill("");
  await expect(fileInput).toBeDisabled();
  await labelInput.fill("vải");
  await expect(page.locator(".path-line").filter({ hasText: /Textile/i }).first()).toBeVisible();
  await expect(fileInput).toBeEnabled();
  await assertNoHorizontalOverflow(page);
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
