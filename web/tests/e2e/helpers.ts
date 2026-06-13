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
  { path: "/user/dashboard", expected: /Xin chào|Lượng rác hằng ngày|Phân loại gần đây/i },
  { path: "/user/ecopet", expected: /EcoPet|Trợ lý thói quen xanh|Chat với EcoPet/i },
  { path: "/user/advice", expected: /AI Advisor|Gợi ý sức khỏe|Lời khuyên/i },
  { path: "/user/map", expected: /Bản đồ thùng rác|Trạm gần bạn|OpenStreetMap/i },
  { path: "/user/alerts", expected: /Cảnh báo|vấn đề/i },
  { path: "/user/schedule", expected: /Lịch thu gom|Lịch trạm/i },
  { path: "/user/collect", expected: /Đã thu gom|Lịch thu gom/i },
  { path: "/user/report-issue", expected: /Báo lỗi|thiết bị/i },
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
  { tab: "camera", nav: /Camera/i, title: "Camera" },
  { tab: "live", nav: /Giám sát/i, title: "Giám sát" },
  { tab: "history", nav: /Lịch sử/i, title: "Lịch sử" },
  { tab: "bin-map", nav: /Bản đồ/i, title: "Bản đồ" },
  { tab: "alerts", nav: /Cảnh báo/i, title: "Cảnh báo" },
  { tab: "devices", nav: /Thiết bị/i, title: "Thiết bị" },
  { tab: "roles", nav: /Role/i, title: "Role" },
  { tab: "data", nav: /Dữ liệu/i, title: "Dữ liệu" },
  { tab: "training", nav: /Huấn luyện/i, title: "Huấn luyện" },
  { tab: "mapping", nav: /Mapping/i, title: "Mapping" },
  { tab: "model", nav: /Model AI/i, title: "Model AI" },
  { tab: "audio", nav: /Audio/i, title: "Audio" },
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
  await page.goto(targetPath, { waitUntil: "domcontentloaded" });
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

export async function assertReadableFormControls(page: Page): Promise<void> {
  const failures = await page.evaluate(() => {
    function parseRgb(value: string) {
      const match = value.match(/rgba?\(([^)]+)\)/);
      if (!match) return null;
      const parts = match[1].split(",").map((part) => Number.parseFloat(part.trim()));
      if (parts.length < 3) return null;
      return { r: parts[0], g: parts[1], b: parts[2], a: parts[3] ?? 1 };
    }

    function luminance(channel: number) {
      const value = channel / 255;
      return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    }

    function contrast(foreground: string, background: string) {
      const fg = parseRgb(foreground);
      const bg = parseRgb(background);
      if (!fg || !bg || fg.a < 0.08) return 21;
      const l1 = 0.2126 * luminance(fg.r) + 0.7152 * luminance(fg.g) + 0.0722 * luminance(fg.b);
      const l2 = 0.2126 * luminance(bg.r) + 0.7152 * luminance(bg.g) + 0.0722 * luminance(bg.b);
      return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    }

    function effectiveBackground(element: Element) {
      let current: Element | null = element;
      while (current) {
        const background = window.getComputedStyle(current).backgroundColor;
        const parsed = parseRgb(background);
        if (parsed && parsed.a > 0.2) return background;
        current = current.parentElement;
      }
      return window.getComputedStyle(document.body).backgroundColor;
    }

    return Array.from(document.querySelectorAll("input, select, textarea, button"))
      .map((element) => {
        const htmlElement = element as HTMLElement;
        const rect = htmlElement.getBoundingClientRect();
        const style = window.getComputedStyle(htmlElement);
        const visibleText = (htmlElement.textContent || "").trim();
        const text = visibleText || htmlElement.getAttribute("aria-label") || "";
        const isVisible =
          rect.width > 4 &&
          rect.height > 4 &&
          style.visibility !== "hidden" &&
          style.display !== "none" &&
          Number.parseFloat(style.opacity || "1") > 0.08;
        if (!isVisible) return null;
        const background = effectiveBackground(htmlElement);
        const textRatio = contrast(style.color, background);
        const placeholderColor = window.getComputedStyle(htmlElement, "::placeholder").color;
        const placeholderRatio = placeholderColor ? contrast(placeholderColor, background) : 21;
        const needsTextCheck = element.tagName !== "BUTTON" || visibleText.length > 0;
        if (needsTextCheck && textRatio < 3) {
          return {
            cls: htmlElement.className,
            color: style.color,
            background,
            ratio: Number(textRatio.toFixed(2)),
            tag: element.tagName,
            text
          };
        }
        if (element.tagName !== "BUTTON" && htmlElement.getAttribute("placeholder") && placeholderRatio < 3) {
          return {
            cls: htmlElement.className,
            color: placeholderColor,
            background,
            ratio: Number(placeholderRatio.toFixed(2)),
            tag: `${element.tagName}::placeholder`,
            text: htmlElement.getAttribute("placeholder") || ""
          };
        }
        return null;
      })
      .filter(Boolean)
      .slice(0, 10);
  });
  expect(failures, JSON.stringify(failures, null, 2)).toEqual([]);
}

export async function assertNoTopbarOverlap(page: Page): Promise<void> {
  const overlaps = await page.evaluate(() => {
    function visibleChildren(selector: string) {
      const parent = document.querySelector(selector);
      if (!parent) return [];
      return Array.from(parent.children)
        .map((element) => {
          const rect = element.getBoundingClientRect();
          const style = window.getComputedStyle(element);
          return {
            bottom: rect.bottom,
            cls: typeof (element as HTMLElement).className === "string" ? (element as HTMLElement).className : "",
            display: style.display,
            height: rect.height,
            left: rect.left,
            right: rect.right,
            text: (element.textContent || "").replace(/\s+/g, " ").trim().slice(0, 48),
            top: rect.top,
            visibility: style.visibility,
            width: rect.width
          };
        })
        .filter((item) => item.display !== "none" && item.visibility !== "hidden" && item.width > 3 && item.height > 3);
    }

    const found = [];
    for (const items of [visibleChildren(".topbar"), visibleChildren(".topbar-actions")]) {
      for (let i = 0; i < items.length; i += 1) {
        for (let j = i + 1; j < items.length; j += 1) {
          const a = items[i];
          const b = items[j];
          const overlapX = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
          const overlapY = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
          if (overlapX > 3 && overlapY > 3) {
            found.push({ a, b, overlapX: Math.round(overlapX), overlapY: Math.round(overlapY) });
          }
        }
      }
    }
    return found.slice(0, 8);
  });
  expect(overlaps, JSON.stringify(overlaps, null, 2)).toEqual([]);
}

export async function assertChatbotDoesNotCover(page: Page, targetSelector: string): Promise<void> {
  const overlap = await page.evaluate((selector) => {
    const target = document.querySelector(selector);
    const launcher = document.querySelector(".chatbot-pet-trigger, .chat-panel-dock");
    if (!target || !launcher) return null;
    const targetRect = target.getBoundingClientRect();
    const launcherRect = launcher.getBoundingClientRect();
    const overlapX = Math.max(0, Math.min(targetRect.right, launcherRect.right) - Math.max(targetRect.left, launcherRect.left));
    const overlapY = Math.max(0, Math.min(targetRect.bottom, launcherRect.bottom) - Math.max(targetRect.top, launcherRect.top));
    const overlapArea = overlapX * overlapY;
    const targetArea = Math.max(1, targetRect.width * targetRect.height);
    return {
      ratio: overlapArea / targetArea,
      overlapX: Math.round(overlapX),
      overlapY: Math.round(overlapY),
      target: {
        bottom: Math.round(targetRect.bottom),
        left: Math.round(targetRect.left),
        right: Math.round(targetRect.right),
        top: Math.round(targetRect.top)
      }
    };
  }, targetSelector);
  if (overlap) {
    expect(overlap.ratio, JSON.stringify(overlap, null, 2)).toBeLessThan(0.05);
  }
}

export async function assertUserShellHasNoAdminControls(page: Page): Promise<void> {
  const nav = page.getByRole("navigation", { name: /User navigation/i });
  await expect(nav).toBeVisible();
  await expect(nav).not.toContainText(/Camera/i);
  await expect(nav).not.toContainText(/Giám sát|Mapping|Cài đặt/i);
  await expect(page.locator(".camera-frame, .stream-card, .dataset-grid, .camera-management-grid, .camera-config-panel")).toHaveCount(0);
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
