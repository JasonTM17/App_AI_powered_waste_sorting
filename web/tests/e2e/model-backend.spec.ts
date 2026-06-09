import { expect, test } from "@playwright/test";

import { agentFetch, agentJson, loginViaAgent } from "./helpers";

type RuntimeStatus = {
  camera: { running: boolean; connected: boolean; message: string };
  model: { running: boolean; connected: boolean; message: string };
  three_bin_classifier: { running: boolean; connected: boolean; message: string };
};

type ModelClassesResponse = {
  classes: Array<{ id: number; name: string }>;
};

type CommonWasteCatalogResponse = {
  items: Array<{ canonical_class: string; command: string; bin_index: number; route_label: string }>;
};

type UserAnalyticsResponse = {
  total: number;
  range_days: number;
  route_totals: Array<{ command: "O" | "R" | "I"; route_label: string; bin_index: number; count: number }>;
  recent_classifications: Array<{ cls_name: string }>;
};

test("Admin model/status APIs expose classifier state and class routes", async () => {
  const admin = await loginViaAgent("admin");

  const status = await agentJson<RuntimeStatus>("/api/status", admin.token);
  expect(status.camera).toBeTruthy();
  expect(status.model).toBeTruthy();
  expect(status.three_bin_classifier).toBeTruthy();

  const modelClasses = await agentJson<ModelClassesResponse>("/api/model/classes", admin.token);
  expect(modelClasses.classes.length).toBeGreaterThan(0);

  const catalog = await agentJson<CommonWasteCatalogResponse>("/api/common-waste/catalog", admin.token);
  const commands = new Set(catalog.items.map((item) => item.command));
  expect(commands.has("O")).toBe(true);
  expect(commands.has("R")).toBe(true);
  expect(commands.has("I")).toBe(true);
  expect(catalog.items.some((item) => item.canonical_class === "Plastic bottle" && item.command === "I")).toBe(true);
  expect(catalog.items.some((item) => item.canonical_class === "Organic" && item.command === "O")).toBe(true);
});

test("User analytics API is owned, aggregated, and excludes other-user history", async () => {
  const user = await loginViaAgent("user");
  const analytics = await agentJson<UserAnalyticsResponse>("/api/user/analytics?range_days=180", user.token);

  expect(analytics.range_days).toBe(180);
  expect(analytics.total).toBeGreaterThanOrEqual(15);
  expect(analytics.route_totals.map((item) => item.command).sort()).toEqual(["I", "O", "R"]);
  const classes = analytics.recent_classifications.map((item) => item.cls_name);
  expect(classes).toContain("Plastic bottle");
  expect(classes).not.toContain("Electronics");
  expect(classes).not.toContain("Cigarette");
});

test("User cannot call Admin model/status surfaces", async () => {
  const user = await loginViaAgent("user");
  for (const path of ["/api/status", "/api/model/classes", "/api/common-waste/catalog", "/api/history"]) {
    const res = await agentFetch(path, user.token);
    expect(res.status, path).toBe(403);
  }
});
