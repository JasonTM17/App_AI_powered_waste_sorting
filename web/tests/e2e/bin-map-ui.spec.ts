import { expect, test, type Locator } from "@playwright/test";

import {
  agentJson,
  assertChatbotDoesNotCover,
  assertNoHorizontalOverflow,
  assertNoTopbarOverlap,
  assertReadableFormControls,
  collectConsoleErrors,
  expectNoConsoleErrors,
  openAppAs
} from "./helpers";

type BinMapStation = {
  station_id: string;
  name: string;
  latitude: number;
  longitude: number;
  coordinate_verified: boolean;
  open_alert_total: number;
  owner_username?: string;
  area: string;
  address?: string;
  bins: Array<{ bin_id: string; command: string; label?: string; fill_percent?: number }>;
};

type BinMapResponse = {
  stations: BinMapStation[];
  center: { latitude: number; longitude: number; zoom: number };
};

function coordinateStationCount(mapData: BinMapResponse) {
  return mapData.stations.filter((station) => Number.isFinite(station.latitude) && Number.isFinite(station.longitude)).length;
}

async function elementBox(locator: Locator) {
  return locator.evaluate((element: HTMLElement) => {
    const rect = element.getBoundingClientRect();
    return {
      top: rect.top,
      bottom: rect.bottom,
      left: rect.left,
      right: rect.right,
      width: rect.width,
      height: rect.height
    };
  });
}

test.describe("Bin map UI/UX", () => {
  test("admin map renders Leaflet frame with station markers and fallback list", async ({ page }) => {
    const consoleErrors = collectConsoleErrors(page);
    const session = await openAppAs(page, "admin", "/admin?tab=bin-map");

    await page.waitForSelector(".operations-map-frame", { state: "visible", timeout: 15000 });

    const mapFrame = page.locator(".operations-map-frame");
    await expect(mapFrame).toBeVisible();
    const mapBox = await elementBox(mapFrame);
    expect(mapBox.height).toBeGreaterThan(200);

    const mapData = await agentJson<BinMapResponse>("/api/admin/bin-map", session.token);
    expect(mapData.stations.length).toBeGreaterThan(0);
    const markerTotal = coordinateStationCount(mapData);

    await expect(page.getByTestId("map-station-count")).toContainText(`${mapData.stations.length}`);
    await expect(page.getByTestId("map-marker-count")).toContainText(`${markerTotal}/${markerTotal} marker`);
    await expect(page.locator(".operations-map-marker")).toHaveCount(markerTotal);
    await expect(page.locator(".operations-station-row")).toHaveCount(mapData.stations.length);

    const firstStation = mapData.stations[0];
    const firstRow = page.locator(".operations-station-row").first();
    await expect(firstRow).toContainText(firstStation.name);

    await assertReadableFormControls(page);
    await assertNoTopbarOverlap(page);
    await assertChatbotDoesNotCover(page, ".operations-map-frame");
    await assertNoHorizontalOverflow(page);
    expectNoConsoleErrors(consoleErrors.filter((err) => !err.includes("net::ERR_FAILED")));
  });

  test("admin map cleanup does not log React root unmount errors when leaving the route", async ({ page }) => {
    const consoleErrors = collectConsoleErrors(page);
    await openAppAs(page, "admin", "/admin?tab=bin-map");
    await page.waitForSelector(".operations-map-frame", { state: "visible", timeout: 15000 });

    await page.goto("/admin?tab=live", { waitUntil: "domcontentloaded" });
    await expect(page.locator(".page-heading h1")).toHaveText("Giám sát");

    expect(consoleErrors.join("\n")).not.toContain("Attempted to synchronously unmount a root");
    expectNoConsoleErrors(consoleErrors.filter((err) => !err.includes("net::ERR_FAILED")));
  });

  test("admin map shows tile error fallback when OSM is unreachable", async ({ page }) => {
    await page.route("**tile.openstreetmap.org/**", (route) => route.abort());
    const consoleErrors = collectConsoleErrors(page);
    const session = await openAppAs(page, "admin", "/admin?tab=bin-map");

    await page.waitForSelector(".operations-map-frame", { state: "visible", timeout: 15000 });

    await expect(page.locator(".alert.compact-alert")).toContainText(/Tile bản đồ chưa tải được/i);

    const mapData = await agentJson<BinMapResponse>("/api/admin/bin-map", session.token);
    await expect(page.locator(".operations-station-row")).toHaveCount(mapData.stations.length);
    await assertReadableFormControls(page);
    await assertNoHorizontalOverflow(page);
    expectNoConsoleErrors(consoleErrors.filter((err) => !err.includes("net::ERR_FAILED")));
  });

  test("admin map station row click selects station", async ({ page }) => {
    await openAppAs(page, "admin", "/admin?tab=bin-map");
    await page.waitForSelector(".operations-station-row", { state: "visible", timeout: 15000 });

    const rows = page.locator(".operations-station-row");
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThan(0);

    const secondRow = rows.nth(1);
    const stationName = await secondRow.locator("strong").textContent();
    await secondRow.click();

    await expect(rows.nth(1)).toHaveClass(/active/);
    await expect(page.locator(".operations-station-row.active strong")).toContainText(stationName ?? "");
  });

  test("admin map refresh button triggers data reload", async ({ page }) => {
    await openAppAs(page, "admin", "/admin?tab=bin-map");
    await page.waitForSelector(".operations-map-frame", { state: "visible", timeout: 15000 });

    const refreshButton = page.getByTitle("Làm mới bản đồ");
    await expect(refreshButton).toBeVisible();

    const responsePromise = page.waitForResponse((response) => response.url().includes("/api/admin/bin-map"));
    await refreshButton.click();
    const response = await responsePromise;
    expect(response.status()).toBe(200);
  });

  test("user map page renders with OpenStreetMap heading and station list", async ({ page }) => {
    const consoleErrors = collectConsoleErrors(page);
    const session = await openAppAs(page, "user", "/user/map");

    await expect(page.locator("body")).toContainText(/Bản đồ thùng rác/i);
    await expect(page.locator("body")).toContainText(/OpenStreetMap/i);

    const mapData = await agentJson<BinMapResponse>("/api/user/bin-map", session.token);
    expect(mapData.stations.length).toBeGreaterThan(0);
    const markerTotal = coordinateStationCount(mapData);
    await expect(page.getByTestId("map-station-count")).toContainText(`${mapData.stations.length}`);
    await expect(page.getByTestId("map-marker-count")).toContainText(`${markerTotal}/${markerTotal} marker`);
    await expect(page.locator(".operations-station-row")).toHaveCount(mapData.stations.length);

    await assertReadableFormControls(page);
    await assertNoTopbarOverlap(page);
    await assertChatbotDoesNotCover(page, ".operations-map-frame");
    await assertNoHorizontalOverflow(page);
    expectNoConsoleErrors(consoleErrors.filter((err) => !err.includes("net::ERR_FAILED")));
  });

  test("user map shows station details: verified status, owner, alert count", async ({ page }) => {
    const session = await openAppAs(page, "user", "/user/map");
    const mapData = await agentJson<BinMapResponse>("/api/user/bin-map", session.token);

    const verifiedStation = mapData.stations.find((s) => s.coordinate_verified);
    const candidateStation = mapData.stations.find((s) => !s.coordinate_verified);

    if (verifiedStation) {
      await expect(page.locator(".operations-station-row").first()).toContainText(/tọa độ đã xác minh/i);
    }
    if (candidateStation) {
      await expect(page.locator("[data-testid='bin-map-fallback-list']")).toContainText(/tọa độ ứng viên/i);
    }

    const stationWithOwner = mapData.stations.find((s) => s.owner_username);
    if (stationWithOwner) {
      await expect(page.locator("[data-testid='bin-map-fallback-list']")).toContainText(stationWithOwner.owner_username!);
    }
  });

  test("user map is responsive on mobile viewport", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    const consoleErrors = collectConsoleErrors(page);
    await openAppAs(page, "user", "/user/map");

    await expect(page.locator("body")).toContainText(/Bản đồ thùng rác/i);
    const mapFrame = page.locator(".operations-map-frame");
    await expect(mapFrame).toBeVisible();
    const box = await elementBox(mapFrame);
    expect(box.top).toBeLessThan(360);
    expect(box.bottom).toBeGreaterThan(360);
    await expect(page.locator(".operations-station-row").first()).toBeVisible();

    await assertReadableFormControls(page);
    await assertChatbotDoesNotCover(page, ".operations-map-frame");
    await assertNoHorizontalOverflow(page);
    expectNoConsoleErrors(consoleErrors.filter((err) => !err.includes("net::ERR_FAILED")));
  });

  test("user map lets the page scroll over the map until focus mode is opened", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openAppAs(page, "user", "/user/map");

    const mapFrame = page.locator(".operations-map-frame");
    await expect(mapFrame).toBeVisible();
    await expect(mapFrame).toHaveAttribute("data-gesture-mode", "page-scroll");
    const box = await elementBox(mapFrame);
    await page.mouse.move(box.left + box.width / 2, box.top + Math.min(120, box.height / 2));
    await page.mouse.wheel(0, 520);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(20);

    await page.getByTitle("Mở rộng bản đồ").click();
    await expect(mapFrame).toHaveAttribute("data-gesture-mode", "map");
  });

  test("user map keeps map content above the fold on compact mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const consoleErrors = collectConsoleErrors(page);
    await openAppAs(page, "user", "/user/map");

    await expect(page.locator(".user-hero-summary")).toHaveCount(0);
    await expect(page.locator(".user-range-row")).toHaveCount(0);
    await expect(page.locator(".user-agent-card")).toBeHidden();

    const mapFrame = page.locator(".operations-map-frame");
    await expect(mapFrame).toBeVisible();
    const box = await elementBox(mapFrame);
    expect(box.top).toBeLessThan(360);
    expect(box.bottom).toBeGreaterThan(420);

    await assertReadableFormControls(page);
    await assertChatbotDoesNotCover(page, ".operations-map-frame");
    await assertNoHorizontalOverflow(page);
    expectNoConsoleErrors(consoleErrors.filter((err) => !err.includes("net::ERR_FAILED")));
  });

  test("map warns clearly when stations have no valid coordinates", async ({ page }) => {
    await page.route("**/api/user/bin-map", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          generated_at: "2026-06-12T00:00:00Z",
          center: { latitude: 10.855, longitude: 106.765, zoom: 13 },
          stations: [
            {
              station_id: "missing-coordinates",
              name: "Trạm thiếu tọa độ",
              area: "Thu Duc",
              address: "Pending verification",
              coordinate_verified: false,
              open_alert_total: 0,
              owner_username: "user",
              bins: [
                {
                  bin_id: "missing-coordinates-R",
                  station_id: "missing-coordinates",
                  command: "R",
                  bin_index: 2,
                  label: "Tái chế",
                  fill_percent: 62,
                  status: "warning",
                  active: true,
                  updated_at: "2026-06-12T00:00:00Z"
                }
              ]
            }
          ],
          total: 1
        })
      })
    );

    await openAppAs(page, "user", "/user/map");

    await expect(page.getByTestId("map-station-count")).toContainText("1");
    await expect(page.getByTestId("map-marker-count")).toContainText("0/0 marker");
    await expect(page.getByTestId("map-coordinate-count")).toContainText("1");
    await expect(page.locator(".alert.compact-alert")).toContainText(/fallback|tọa độ/i);
    await page.locator(".operations-station-row").click();
    await expect(page.locator(".operations-station-row")).toContainText("Trạm thiếu tọa độ");
    await expect(page.getByTestId("user-map-station-detail")).toContainText(/Chưa có tọa độ hợp lệ/i);
    await expect(page.getByTestId("user-map-station-detail")).toContainText(/62%/);
    await assertNoHorizontalOverflow(page);
  });

  test("map empty state renders when no data", async ({ page }) => {
    await page.route("**/api/user/bin-map", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          stations: [],
          center: { latitude: 10.855, longitude: 106.765, zoom: 13 }
        })
      })
    );

    await openAppAs(page, "user", "/user/map");
    await expect(page.locator(".operations-map-card.empty-state")).toContainText(/Chưa có dữ liệu bản đồ/i);
  });

  test("user map auto-refreshes station fullness without a manual click", async ({ page }) => {
    let requestCount = 0;
    await page.route("**/api/user/bin-map", (route) => {
      requestCount += 1;
      const fill = requestCount > 1 ? 87 : 31;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          generated_at: `2026-06-12T00:00:0${Math.min(requestCount, 9)}Z`,
          center: { latitude: 10.855, longitude: 106.765, zoom: 13 },
          stations: [
            {
              id: 1,
              station_id: "auto-refresh-station",
              name: "Trạm realtime tự động",
              area: "Thu Duc",
              address: "Realtime test",
              latitude: 10.855,
              longitude: 106.765,
              coordinate_verified: true,
              status: "active",
              active: true,
              owner_username: "user",
              device_id: "device-1",
              note: "",
              seed_source: "test",
              alert_total: 0,
              open_alert_total: 0,
              created_at: "2026-06-12T00:00:00Z",
              updated_at: "2026-06-12T00:00:00Z",
              bins: [
                {
                  id: 1,
                  bin_id: "auto-refresh-R",
                  station_id: "auto-refresh-station",
                  command: "R",
                  bin_index: 2,
                  label: "Tái chế",
                  fill_percent: fill,
                  status: fill > 80 ? "full" : "normal",
                  active: true,
                  updated_at: "2026-06-12T00:00:00Z"
                }
              ]
            }
          ],
          total: 1
        })
      });
    });

    await openAppAs(page, "user", "/user/map");

    await expect(page.getByTestId("map-refresh-status")).toContainText(/Vừa cập nhật|Chờ dữ liệu realtime|Đang cập nhật/i);
    await expect(page.getByTestId("user-map-station-detail")).toBeVisible();
    const requestCountAfterLoad = requestCount;
    await expect.poll(() => requestCount, { timeout: 9000, intervals: [500, 1000] }).toBeGreaterThan(requestCountAfterLoad);
    await expect(page.getByTestId("user-map-station-detail")).toContainText(/87%/);
    await assertNoHorizontalOverflow(page);
  });

  test("popup card shows bin fill levels when marker clicked", async ({ page }) => {
    await openAppAs(page, "user", "/user/map");
    await page.waitForSelector(".operations-map-frame", { state: "visible", timeout: 15000 });

    const marker = page.locator(".operations-map-marker").first();
    await expect(marker).toBeVisible();
    await marker.click();

    const popup = page.locator(".operations-map-popup-card");
    await expect(popup).toBeVisible();
    await expect(popup).toContainText(/Phụ trách/i);
    await expect(popup).toContainText(/Tọa độ/i);
    await expect(popup).toContainText(/Cảnh báo mở/i);
  });

  test("map frame has correct height on desktop", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await openAppAs(page, "user", "/user/map");
    await page.waitForSelector(".operations-map-frame", { state: "visible", timeout: 15000 });

    const mapFrame = page.locator(".operations-map-frame");
    const box = await elementBox(mapFrame);
    expect(box.height).toBeGreaterThanOrEqual(300);
    expect(box.height).toBeLessThanOrEqual(700);
  });

  test("map can expand into focus mode for tracking", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openAppAs(page, "user", "/user/map");
    await page.waitForSelector(".operations-map-frame", { state: "visible", timeout: 15000 });

    const mapCard = page.locator(".operations-map-card");
    const mapFrame = page.locator(".operations-map-frame");
    const before = await elementBox(mapFrame);

    await page.getByTitle("Mở rộng bản đồ").click();
    await expect(mapCard).toHaveClass(/is-expanded/);
    await page.waitForTimeout(120);

    const after = await elementBox(mapFrame);
    expect(after.height).toBeGreaterThan(before.height);
    expect(after.width).toBeGreaterThan(before.width);
    await assertChatbotDoesNotCover(page, ".operations-map-frame");

    await page.getByTitle("Thu nhỏ bản đồ").click();
    await expect(mapCard).not.toHaveClass(/is-expanded/);
  });
});
