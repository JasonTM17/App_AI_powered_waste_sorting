import { expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

export const SESSION_TOKEN_KEY = "trash-sorter-session-token";
export const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://127.0.0.1:8875";

export type QaRole = "admin" | "user" | "other" | "temporary_admin";

type LoginResponse = {
  token: string;
  role: "admin" | "user";
  username: string;
  capabilities: string[];
  expires_at: string;
};

type QaState = {
  accounts: Record<QaRole, { username: string; password: string }>;
  paths: Record<string, string>;
  seed: Record<string, unknown>;
};

export const userRoutes = [
  { path: "/user/dashboard", expected: /Xin chào|Daily Waste Volume|Recent Classifications/i },
  { path: "/user/ecopet", expected: /EcoPet|Daily Waste Volume|Trợ lý AI/i },
  { path: "/user/advice", expected: /AI Advisor|Gợi ý sức khỏe|Lời khuyên/i },
  { path: "/user/history", expected: /Lịch sử của bạn|Phân loại gần đây/i },
  { path: "/user/device", expected: /Thiết bị|Trạng thái thùng|EcoSort QA Station/i },
  { path: "/user/analytics", expected: /Xu hướng|Cơ cấu 3 thùng|Biểu đồ cột/i },
  { path: "/user/reports", expected: /CSV an toàn cho người dùng|Báo cáo/i },
  { path: "/user/notifications", expected: /Trung tâm thông báo|Nhắc việc local/i },
  { path: "/user/community", expected: /Eco-Share local|Cộng đồng/i },
  { path: "/user/leaderboard", expected: /Bảng xếp hạng local|Mốc so sánh/i },
  { path: "/user/account", expected: /Tài khoản|Đổi mật khẩu/i }
];

export const adminTabs = [
  { tab: "live", nav: /Giám sát/i, title: "Giám sát" },
  { tab: "history", nav: /Lịch sử/i, title: "Lịch sử" },
  { tab: "data", nav: /Dữ liệu/i, title: "Dữ liệu" },
  { tab: "mapping", nav: /Mapping/i, title: "Mapping" },
  { tab: "settings", nav: /Cài đặt/i, title: "Cài đặt" },
  { tab: "logs", nav: /Nhật ký/i, title: "Nhật ký" },
  { tab: "accounts", nav: /Tài khoản/i, title: "Tài khoản" },
  { tab: "reports", nav: /Báo cáo/i, title: "Báo cáo" }
];

export function readQaState(): QaState {
  const statePath = path.resolve(__dirname, "..", "..", ".playwright-tmp", "state.json");
  return JSON.parse(fs.readFileSync(statePath, "utf-8")) as QaState;
}

export async function loginViaAgent(role: QaRole): Promise<LoginResponse> {
  const credentials = readQaState().accounts[role];
  const res = await fetch(`${AGENT_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials)
  });
  if (!res.ok) {
    throw new Error(`Login failed for ${role}: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as LoginResponse;
}

export async function openAppAs(page: Page, role: "admin" | "user", targetPath: string): Promise<LoginResponse> {
  const session = await loginViaAgent(role);
  await page.addInitScript(
    ([key, token]) => {
      window.localStorage.setItem(key, token);
    },
    [SESSION_TOKEN_KEY, session.token]
  );
  await page.goto(targetPath, { waitUntil: "networkidle" });
  await expect(page.locator("body")).toBeVisible();
  return session;
}

export async function agentFetch(pathname: string, token: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${AGENT_URL}${pathname}`, { ...init, headers });
}

export async function agentJson<T>(pathname: string, token: string, init: RequestInit = {}): Promise<T> {
  const res = await agentFetch(pathname, token, init);
  if (!res.ok) {
    throw new Error(`Agent request failed ${pathname}: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as T;
}

export async function assertNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => {
    const root = document.documentElement;
    return Math.max(0, root.scrollWidth - window.innerWidth);
  });
  if (overflow > 3) {
    const diagnostics = await page.evaluate(() => {
      const viewport = window.innerWidth;
      return Array.from(document.querySelectorAll("body *"))
        .map((element) => {
          const rect = element.getBoundingClientRect();
          return {
            cls: typeof element.className === "string" ? element.className : "",
            left: Math.round(rect.left),
            right: Math.round(rect.right),
            tag: element.tagName,
            text: (element.textContent || "").replace(/\s+/g, " ").trim().slice(0, 72),
            width: Math.round(rect.width)
          };
        })
        .filter((item) => item.right > viewport + 3 || item.left < -3 || item.width > viewport + 3)
        .sort((a, b) => b.width - a.width)
        .slice(0, 10);
    });
    throw new Error(
      `Horizontal overflow ${overflow}px. Viewport ${await page.evaluate(() => window.innerWidth)}. ` +
        `Wide elements: ${JSON.stringify(diagnostics)}`
    );
  }
}

export async function assertUserShellHasNoAdminControls(page: Page): Promise<void> {
  const nav = page.getByRole("navigation", { name: /User navigation/i });
  await expect(nav).toBeVisible();
  await expect(nav).not.toContainText(/Giám sát|Mapping|Cài đặt/i);
  await expect(page.locator(".camera-frame, .stream-card, .dataset-grid")).toHaveCount(0);
}

export async function assertStitchPetLauncher(page: Page, open: boolean): Promise<void> {
  const pet = page.getByRole("button", { name: /Mở trợ lý AI/i });
  if (open) {
    await expect(page.locator(".chat-panel-dock[role='dialog']")).toBeVisible();
    await expect(page.locator(".stitch-chat-header")).toContainText(/EcoPet|Trợ lý vận hành/i);
    await expect(pet).toHaveCount(0);
    return;
  }
  await expect(pet).toBeVisible();
  const bounds = await pet.boundingBox();
  expect(bounds).not.toBeNull();
  expect(bounds!.width).toBeGreaterThanOrEqual(52);
  expect(bounds!.width).toBeLessThanOrEqual(60);
}

export async function assertUserChartsRender(page: Page): Promise<void> {
  const lineChart = page.locator(".user-line-chart");
  await expect(lineChart).toBeVisible();
  const nonBlank = await lineChart.evaluate((svg) => {
    const box = svg.getBoundingClientRect();
    return box.width > 120 && box.height > 80 && svg.querySelectorAll("path, polyline, circle").length > 0;
  });
  expect(nonBlank).toBe(true);
}

export function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      const text = message.text();
      if (!/favicon/i.test(text)) {
        errors.push(text);
      }
    }
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

export function expectNoConsoleErrors(errors: string[]): void {
  expect(errors, errors.join("\n")).toEqual([]);
}
