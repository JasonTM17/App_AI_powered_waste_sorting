import { expect, test } from "@playwright/test";

import {
  adminTabs,
  agentFetch,
  assertChatbotDoesNotCover,
  assertNoHorizontalOverflow,
  assertNoTopbarOverlap,
  assertReadableFormControls,
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
  await assertReadableFormControls(page);

  await page.getByLabel(/Tên đăng nhập/i).fill(state.accounts.admin.username);
  await page.getByLabel(/^Mật khẩu$/i).fill(state.accounts.admin.password);
  await page.getByRole("button", { name: /^Đăng nhập$/i }).click();

  await expect(page.getByRole("navigation", { name: /Main navigation/i })).toContainText(/Giám sát/i);
  await expect(page.locator(".page-heading h1")).toHaveText("Giám sát");
  await page.getByRole("button", { name: /Thu gọn thanh điều hướng/i }).click();
  await expect(page.locator(".app-shell")).toHaveClass(/sidebar-collapsed/);
  if ((page.viewportSize()?.width ?? 0) > 760) {
    const collapsedSidebar = await page.locator(".sidebar").evaluate((sidebar) => {
      const nav = sidebar.querySelector(".nav-list") as HTMLElement | null;
      const items = Array.from(sidebar.querySelectorAll(".nav-item")) as HTMLElement[];
      const navStyle = nav ? window.getComputedStyle(nav) : null;
      return {
        itemOverflow: items.some((item) => item.scrollWidth > item.clientWidth + 1),
        navClientWidth: nav?.clientWidth ?? 0,
        navOverflowX: navStyle?.overflowX ?? "",
        navScrollbarWidth: navStyle?.scrollbarWidth ?? "",
        navScrollWidth: nav?.scrollWidth ?? 0
      };
    });
    expect(collapsedSidebar.navOverflowX).toBe("hidden");
    expect(collapsedSidebar.navScrollbarWidth).toBe("none");
    expect(collapsedSidebar.itemOverflow).toBe(false);
    expect(collapsedSidebar.navScrollWidth).toBeLessThanOrEqual(collapsedSidebar.navClientWidth + 1);
  }
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.locator(".app-shell")).toHaveClass(/sidebar-collapsed/);
  await assertNoHorizontalOverflow(page);
  await assertNoTopbarOverlap(page);
  expectNoConsoleErrors(consoleErrors);
});

test("user session sees only User dashboard and is forbidden from Admin APIs", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const session = await openAppAs(page, "user", "/user/dashboard");

  await expect(page.locator("body")).toContainText(/Xin chào|Lượng rác hằng ngày|Phân loại gần đây/i);
  await assertStitchPetLauncher(page, false);
  await assertUserShellHasNoAdminControls(page);
  await assertReadableFormControls(page);
  await assertNoTopbarOverlap(page);
  await assertChatbotDoesNotCover(page, ".user-dashboard-grid");

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
    await assertReadableFormControls(page);
    await assertNoTopbarOverlap(page);
    await assertNoHorizontalOverflow(page);
  }

  expectNoConsoleErrors(consoleErrors);
});

test("admin Camera tab exposes desktop-equivalent USB and ROI controls", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await openAppAs(page, "admin", "/admin?tab=camera");

  await expect(page.locator(".page-heading h1")).toHaveText("Camera");
  await expect(page.locator(".camera-management-grid")).toBeVisible();
  await expect(page.locator(".camera-stage")).toBeVisible();
  await expect(page.locator(".diagnostic-list")).toContainText(/FPS|Backend|Mean brightness|Non-black/);
  await expect(page.locator(".camera-config-panel")).toContainText(/USB only|ROI X|ROI width|ROI height/);
  await expect(page.locator(".camera-config-panel input[type='number']")).toHaveCount(6);
  await expect(page.locator(".camera-config-panel input[type='checkbox']")).toHaveCount(3);
  await assertReadableFormControls(page);
  await assertNoTopbarOverlap(page);

  const widthInput = page.locator(".camera-config-panel input[type='number']").first();
  const beforeWheel = await widthInput.inputValue();
  await widthInput.focus();
  await widthInput.dispatchEvent("wheel", { deltaY: -120 });
  await expect(widthInput).toHaveValue(beforeWheel);
  await expect(widthInput).not.toBeFocused();

  await assertNoHorizontalOverflow(page);
  await assertChatbotDoesNotCover(page, ".camera-config-panel");
  expectNoConsoleErrors(consoleErrors);
});

test("training tab requires a canonical label before phone/manual upload", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  await openAppAs(page, "admin", "/admin?tab=training");

  await expect(page.locator(".page-heading h1")).toHaveText("Huấn luyện");
  const labelInput = page.getByLabel(/^Nhãn$/i);
  const fileInput = page.locator('input[type="file"][accept="image/*"]').last();
  await expect(labelInput).toHaveValue("Pen");
  await expect(fileInput).toBeEnabled();
  await labelInput.fill("");
  await expect(fileInput).toBeDisabled();
  await labelInput.fill("vải");
  await expect(page.locator(".path-line").filter({ hasText: /Textile/i }).first()).toBeVisible();
  await expect(fileInput).toBeEnabled();
  await assertReadableFormControls(page);
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
  await assertNoTopbarOverlap(page);
  expectNoConsoleErrors(consoleErrors);
});
