#!/usr/bin/env node
/**
 * Web audit script for Trash Sorter Pro.
 *
 * Navigates every user + admin route, captures console errors, network 4xx/5xx
 * (with response body, first 2 KB), and a positive DOM assertion per route.
 * Writes JSON to audit/output/audit-{ts}.json (gitignored) and screenshots to
 * audit/screenshots/ (gitignored).
 *
 * Usage (from web/):
 *   node scripts/audit-web.mjs                  # full audit (~5 min)
 *   node scripts/audit-web.mjs --smoke          # 10 highest-traffic routes (<60s, PR CI)
 *   node scripts/audit-web.mjs --role=admin     # admin only
 *   node scripts/audit-web.mjs --role=user      # user only
 *   node scripts/audit-web.mjs --role=all       # all roles (default)
 *   node scripts/audit-web.mjs --help
 *
 * Required env:
 *   WEB_URL   default http://localhost:3000
 *   AGENT_URL default http://localhost:8765
 */
import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../..');
const AUDIT_DIR = path.join(PROJECT_ROOT, 'audit');
const SCREENSHOTS_DIR = path.join(AUDIT_DIR, 'screenshots');
const OUTPUT_DIR = path.join(AUDIT_DIR, 'output');
const WEB_URL = process.env.WEB_URL || 'http://localhost:3000';
const AGENT_URL = process.env.AGENT_URL || 'http://localhost:8765';

const CREDS = {
  admin: {
    username: process.env.ADMIN_USERNAME || 'admin',
    password: process.env.ADMIN_PASSWORD || 'admin123'
  },
  user: {
    username: process.env.USER_USERNAME || 'user',
    password: process.env.USER_PASSWORD || 'user123'
  }
};

const ROUTES = [
  { name: 'root',              path: '/',                    requiredRole: 'public', positiveSelector: 'body' },
  { name: 'admin-root',        path: '/admin',               requiredRole: 'admin',  positiveSelector: 'aside.sidebar' },
  { name: 'user-dashboard',    path: '/user/dashboard',      requiredRole: 'user',   positiveSelector: 'main.workspace, .user-workspace' },
  { name: 'user-analytics',    path: '/user/analytics',      requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-map',          path: '/user/map',            requiredRole: 'user',   positiveSelector: '.leaflet-container' },
  { name: 'user-alerts',       path: '/user/alerts',         requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-schedule',     path: '/user/schedule',       requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-collect',      path: '/user/collect',        requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-report-issue', path: '/user/report-issue',   requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-history',      path: '/user/history',        requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-device',       path: '/user/device',         requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-ecopet',       path: '/user/ecopet',         requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-advice',       path: '/user/advice',         requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-reports',      path: '/user/reports',        requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-notifications', path: '/user/notifications', requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-community',    path: '/user/community',      requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-leaderboard',  path: '/user/leaderboard',    requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' },
  { name: 'user-account',      path: '/user/account',        requiredRole: 'user',   positiveSelector: 'aside.user-sidebar' }
];

const SMOKE_ROUTES = [
  'root', 'admin-root', 'user-dashboard', 'user-analytics', 'user-history',
  'user-map', 'user-alerts', 'user-account', 'user-reports', 'user-device'
];

const args = process.argv.slice(2);
const opts = {
  smoke: args.includes('--smoke'),
  role: (args.find(a => a.startsWith('--role='))?.split('=')[1]) || 'all',
  help: args.includes('--help')
};

if (opts.help) {
  console.log(`Usage: node scripts/audit-web.mjs [options]

Options:
  --smoke         Run only 10 highest-traffic routes (fast mode for PR CI)
  --role=admin    Audit only admin role
  --role=user     Audit only user role
  --role=all      Audit all roles (default)
  --help          Show this help

Credentials (env vars, dev defaults shown):
  ADMIN_USERNAME  default 'admin'     ADMIN_PASSWORD  default 'admin123'
  USER_USERNAME   default 'user'      USER_PASSWORD   default 'user123'

If dev defaults were changed in auth.db (TRASH_SORTER_AUTH_DEV_DEFAULTS=1 was
not active at agent start), the audit will skip role-protected routes. Set
the env vars above to use the current credentials.

Required services (must be running before audit):
  WEB_URL   default http://localhost:3000  (next dev / next start)
  AGENT_URL default http://localhost:8765  (FastAPI uvicorn)
`);
  process.exit(0);
}

const SENSITIVE_KEYS = new Set([
  'password', 'token', 'session_token', 'authorization', 'auth_token',
  'access_token', 'refresh_token', 'cookie', 'set-cookie', 'secret', 'salt'
]);

function sanitize(value) {
  if (value == null) return value;
  if (Array.isArray(value)) return value.map(sanitize);
  if (typeof value !== 'object') return value;
  const out = {};
  for (const [k, v] of Object.entries(value)) {
    out[k] = SENSITIVE_KEYS.has(k.toLowerCase()) ? '[REDACTED]' : sanitize(v);
  }
  return out;
}

async function login(role) {
  const creds = CREDS[role];
  if (!creds) throw new Error(`Unknown role: ${role}`);
  const res = await fetch(`${AGENT_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(creds)
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Login failed for ${role}: ${res.status} ${body.slice(0, 200)}`);
  }
  const data = await res.json();
  return data.token;
}

// Form-based login: web uses cookie-based session, not bearer token header.
// Visiting / and filling the form establishes a real session in the browser context.
async function formLoginInContext(context, role) {
  const creds = CREDS[role];
  if (!creds) throw new Error(`Unknown role: ${role}`);
  const page = await context.newPage();
  try {
    await page.goto(`${WEB_URL}/`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    const usernameInput = page.locator('input[autocomplete="username"]');
    const isLoginPage = await usernameInput.isVisible({ timeout: 3000 }).catch(() => false);
    if (isLoginPage) {
      await usernameInput.fill(creds.username);
      await page.locator('input[autocomplete="current-password"]').fill(creds.password);
      await Promise.all([
        page.waitForURL((url) => url.pathname !== '/', { timeout: 15000 }).catch(() => null),
        page.locator('button[type="submit"]').click()
      ]);
      // F1 fix: wait for a known post-auth DOM marker so the session cookie
      // has been observed in the browser context. The auth flow lands admin
      // users on /admin (with `aside.sidebar`) and user users on
      // /user/dashboard (with `aside.user-sidebar`).
      const expectedMarker = role === 'admin' ? 'aside.sidebar' : 'aside.user-sidebar';
      await page.locator(expectedMarker).first()
        .waitFor({ state: 'visible', timeout: 10000 })
        .catch(() => null);
      // F1 fix: verify a session cookie was actually set on the context. If
      // the login API sets the cookie on a different response than the form
      // submit triggers, the audit will see a missing cookie and can report it.
      const cookies = await context.cookies();
      const hasSessionCookie = cookies.some(c =>
        /session|token|auth/i.test(c.name) || /session|token|auth/i.test(c.domain)
      );
      if (!hasSessionCookie) {
        console.warn(`[audit] ${role} form login: no session cookie detected on context (cookies: ${cookies.map(c => c.name).join(', ') || 'none'})`);
      }
    }
  } finally {
    await page.close();
  }
}

async function auditRoute(browser, route, role, token) {
  // Form-based login establishes a real session in the browser context (cookie-based).
  // The token arg is kept for backward-compat logging only.
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  if (role && role !== 'public') {
    await formLoginInContext(context, role);
  }
  const page = await context.newPage();
  const findings = {
    route: route.name,
    path: route.path,
    role: role || 'public',
    consoleErrors: [],
    consoleWarnings: [],
    networkErrors: [],
    positiveAssertPassed: false,
    screenshotPath: null,
    durationMs: 0,
    error: null
  };
  const start = Date.now();
  try {
    page.on('console', msg => {
      const text = msg.text();
      if (msg.type() === 'error') findings.consoleErrors.push(text);
      else if (msg.type() === 'warning') findings.consoleWarnings.push(text);
    });
    page.on('response', async res => {
      if (res.status() >= 400) {
        let body = '';
        try { body = (await res.text()).slice(0, 2048); } catch { /* ignore */ }
        findings.networkErrors.push({ url: res.url(), status: res.status(), body });
      }
    });
    await page.goto(`${WEB_URL}${route.path}`, { waitUntil: 'networkidle', timeout: 15000 });
    const sel = route.positiveSelector;
    if (sel) {
      findings.positiveAssertPassed = await page.locator(sel).first().isVisible().catch(() => false);
    } else {
      findings.positiveAssertPassed = true;
    }
    const screenshotFile = path.join(SCREENSHOTS_DIR, `${route.name}-${role || 'public'}.png`);
    await page.screenshot({ path: screenshotFile, fullPage: false });
    findings.screenshotPath = path.relative(PROJECT_ROOT, screenshotFile);
  } catch (e) {
    findings.error = e.message;
  } finally {
    findings.durationMs = Date.now() - start;
    await context.close();
  }
  return findings;
}

async function main() {
  console.log(`[audit] start ${new Date().toISOString()}`);
  console.log(`[audit] web=${WEB_URL} agent=${AGENT_URL} smoke=${opts.smoke} role=${opts.role}`);
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const tokens = {};
  for (const role of ['admin', 'user']) {
    if (opts.role !== 'all' && opts.role !== role) continue;
    try {
      tokens[role] = await login(role);
      console.log(`[audit] API login OK for ${role} (token retained for compatibility; form login is used in browser)`);
    } catch (e) {
      console.error(`[audit] ${role} API login failed (will still try form login): ${e.message}`);
      // Mark as failed for the failure counter, but still try form-based login in auditRoute.
      tokens[role] = null;
    }
  }

  const routeList = opts.smoke ? ROUTES.filter(r => SMOKE_ROUTES.includes(r.name)) : ROUTES;
  const allFindings = [];
  for (const route of routeList) {
    const reqRole = route.requiredRole;
    if (reqRole === 'public') {
      allFindings.push(await auditRoute(browser, route, null, null));
    } else {
      allFindings.push(await auditRoute(browser, route, reqRole, tokens[reqRole] || null));
    }
  }
  await browser.close();

  const output = sanitize({
    generated_at: new Date().toISOString(),
    smoke: opts.smoke,
    role: opts.role,
    total_routes: allFindings.length,
    routes: allFindings
  });
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  const outFile = path.join(OUTPUT_DIR, `audit-${ts}.json`);
  fs.writeFileSync(outFile, JSON.stringify(output, null, 2));
  const failed = allFindings.filter(f =>
    f.error ||
    f.skipped ||
    f.positiveAssertPassed === false ||
    (f.consoleErrors && f.consoleErrors.length > 0)
  ).length;
  console.log(`[audit] ${allFindings.length} routes, ${failed} with issues`);
  console.log(`[audit] output: ${path.relative(PROJECT_ROOT, outFile)}`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
