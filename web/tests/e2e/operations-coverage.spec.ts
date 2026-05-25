import { expect, test } from "@playwright/test";

import {
  agentJson,
  assertNoHorizontalOverflow,
  collectConsoleErrors,
  expectNoConsoleErrors,
  openAppAs
} from "./helpers";

test("user map falls back cleanly when OSM tiles fail", async ({ page }) => {
  await page.route("**tile.openstreetmap.org/**", (route) => route.abort());
  const session = await openAppAs(page, "user", "/user/map");
  const mapData = await agentJson<{ stations: Array<unknown> }>("/api/user/bin-map", session.token);

  await expect(page.locator("body")).toContainText(/Bản đồ thùng rác|Trạm gần bạn/i);
  expect(mapData.stations.length).toBeGreaterThan(0);
  expect(mapData.stations.length).toBeLessThan(10);
  await expect(page.locator(".operations-station-row")).toHaveCount(mapData.stations.length);
  await expect(page.locator(".alert.compact-alert")).toContainText(/Tile bản đồ chưa tải được/i);

  await assertNoHorizontalOverflow(page);
});

test("user can mark a collection complete and report a device issue", async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const session = await openAppAs(page, "user", "/user/collect");

  await page.getByRole("button", { name: /Đã thu gom/i }).first().click();
  await expect(page.locator(".success")).toContainText(/thu gom/i);

  const schedules = await agentJson<{ schedules: Array<{ state: string }> }>(
    "/api/user/collection-schedule",
    session.token
  );
  expect(schedules.schedules.some((item) => item.state === "completed")).toBe(true);

  await page.goto("/user/report-issue", { waitUntil: "domcontentloaded" });
  await page.getByLabel(/Mô tả/i).fill("Camera feed unstable in smoke test");
  await page.getByRole("button", { name: /Gửi báo lỗi/i }).click();
  await expect(page.locator(".success")).toContainText(/báo lỗi/i);

  const alerts = await agentJson<{ alerts: Array<{ alert_id: string }> }>(
    "/api/user/alerts?include_resolved=false",
    session.token
  );
  expect(alerts.alerts.length).toBeGreaterThan(0);

  await assertNoHorizontalOverflow(page);
  expectNoConsoleErrors(consoleErrors);
});
