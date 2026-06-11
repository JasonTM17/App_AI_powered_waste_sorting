import { expect, test } from "@playwright/test";

import { openAppAs } from "./helpers";

test("training tab does not poll dataset-heavy endpoints", async ({ page }) => {
  const agentRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) {
      agentRequests.push(url.pathname);
    }
  });

  await openAppAs(page, "admin", "/admin?tab=training");
  await expect(page.locator(".page-heading h1")).toHaveText("Huấn luyện");
  await expect.poll(() => agentRequests.includes("/api/learn-now/status")).toBe(true);

  expect(agentRequests).toContain("/api/training/status");
  expect(agentRequests).not.toContain("/api/dataset/summary");
  expect(agentRequests).not.toContain("/api/dataset/source-quality");
  expect(agentRequests).not.toContain("/api/dataset/items");
});
