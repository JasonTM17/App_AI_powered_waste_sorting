import { expect, test } from "@playwright/test";

import {
  AGENT_URL,
  assertNoHorizontalOverflow,
  assertStitchPetLauncher,
  assertUserChartsRender,
  assertUserShellHasNoAdminControls,
  collectConsoleErrors,
  expectNoConsoleErrors,
  openAppAs,
  userRoutes
} from "./helpers";

for (const route of userRoutes) {
  test(`User route ${route.path} renders cleanly`, async ({ page }) => {
    const consoleErrors = collectConsoleErrors(page);
    await openAppAs(page, "user", route.path);

    await expect(page.locator("body")).toContainText(route.expected);
    await assertUserShellHasNoAdminControls(page);
    await assertStitchPetLauncher(page, route.path === "/user/ecopet");
    if (route.path === "/user/dashboard" || route.path === "/user/ecopet") {
      await expect(page.locator("body")).toContainText(/Daily Waste Volume|Recent Classifications/i);
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
    await assertNoHorizontalOverflow(page);
  }

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
