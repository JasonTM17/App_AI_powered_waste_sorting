import { defineConfig, devices } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const WEB_ROOT = __dirname;
const PROJECT_ROOT = path.resolve(WEB_ROOT, "..");
const TMP_ROOT = path.join(WEB_ROOT, ".playwright-tmp");
const APPDATA_ROOT = path.join(TMP_ROOT, "appdata");
const XDG_ROOT = path.join(TMP_ROOT, "xdg");
const AGENT_PORT = process.env.TRASH_SORTER_E2E_AGENT_PORT ?? "8875";
const WEB_PORT = process.env.TRASH_SORTER_E2E_WEB_PORT ?? "3100";
const AGENT_URL = `http://127.0.0.1:${AGENT_PORT}`;
const WEB_URL = `http://127.0.0.1:${WEB_PORT}`;
const DEFAULT_VENV_PYTHON =
  process.platform === "win32"
    ? path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
    : path.join(PROJECT_ROOT, ".venv", "bin", "python");
const PYTHON = process.env.TRASH_SORTER_TEST_PYTHON ?? (fs.existsSync(DEFAULT_VENV_PYTHON) ? DEFAULT_VENV_PYTHON : "python");

const testEnv = cleanEnv({
  ...process.env,
  APPDATA: APPDATA_ROOT,
  XDG_CONFIG_HOME: XDG_ROOT,
  NEXT_PUBLIC_AGENT_URL: AGENT_URL,
  TRASH_SORTER_AGENT_PORT: AGENT_PORT,
  TRASH_SORTER_ALLOWED_ORIGINS: WEB_URL,
  TRASH_SORTER_AUTH_DB: path.join(APPDATA_ROOT, "TrashSorter", "auth.db"),
  TRASH_SORTER_AUTH_DEV_DEFAULTS: "0",
  TRASH_SORTER_PLAYWRIGHT_TMP: TMP_ROOT,
  DEEPSEEK_BASE_URL: process.env.DEEPSEEK_BASE_URL ?? "https://api.deepseek.com",
  DEEPSEEK_MODEL: "deepseek-v4-flash",
  DEEPSEEK_TIMEOUT_SECONDS: process.env.DEEPSEEK_TIMEOUT_SECONDS ?? "15"
});

delete testEnv.TRASH_SORTER_AUTH_DATABASE_URL;
delete testEnv.DATABASE_URL;
delete testEnv.TRASH_SORTER_BOOTSTRAP_ADMIN_USERNAME;
delete testEnv.TRASH_SORTER_BOOTSTRAP_ADMIN_PASSWORD;
if (process.env.TRASH_SORTER_REAL_DEEPSEEK_SMOKE !== "1") {
  delete testEnv.DEEPSEEK_API_KEY;
}

execFileSync(PYTHON, ["scripts/seed_playwright_test_data.py"], {
  cwd: PROJECT_ROOT,
  env: testEnv as unknown as NodeJS.ProcessEnv,
  stdio: "inherit"
});

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: {
    timeout: 12_000
  },
  fullyParallel: false,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }]
  ],
  use: {
    baseURL: WEB_URL,
    screenshot: "only-on-failure",
    trace: "retain-on-failure"
  },
  webServer: [
    {
      command: `${quoteShell(PYTHON)} scripts/run_agent.py`,
      cwd: PROJECT_ROOT,
      env: testEnv,
      reuseExistingServer: false,
      timeout: 120_000,
      url: `${AGENT_URL}/api/health`
    },
    {
      command: "npm run build && npm run start:test",
      cwd: WEB_ROOT,
      env: testEnv,
      reuseExistingServer: false,
      timeout: 120_000,
      url: WEB_URL
    }
  ],
  projects: [
    {
      name: "desktop-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 }
      }
    },
    {
      name: "tablet-chromium",
      use: {
        ...devices["Desktop Chrome"],
        hasTouch: true,
        viewport: { width: 820, height: 1180 }
      }
    },
    {
      name: "mobile-chromium",
      use: {
        ...devices["Pixel 5"],
        viewport: { width: 390, height: 844 }
      }
    },
    {
      name: "compact-mobile-chromium",
      use: {
        ...devices["Pixel 5"],
        viewport: { width: 360, height: 740 }
      }
    }
  ]
});

function cleanEnv(env: NodeJS.ProcessEnv): Record<string, string> {
  return Object.fromEntries(
    Object.entries(env).filter((entry): entry is [string, string] => typeof entry[1] === "string")
  );
}

function quoteShell(value: string): string {
  if (!value.includes(" ") && !value.includes("(") && !value.includes(")")) {
    return value;
  }
  return `"${value.replace(/"/g, '\\"')}"`;
}
