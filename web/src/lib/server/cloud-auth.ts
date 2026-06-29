import crypto from "node:crypto";

import { Pool, type QueryResultRow } from "pg";

import { databasePoolConcurrency } from "@/lib/server/db-concurrency";

export type CloudAuthRole = "admin" | "user";

export type CloudAuthIdentity = {
  account_id: number;
  role: CloudAuthRole;
  username: string;
  display_name: string;
  expires_at: string;
  password_default: boolean;
  avatar_path: string;
};

type AccountRow = QueryResultRow & {
  id: number;
  username: string;
  display_name: string | null;
  role: string;
  password_hash: string;
  salt: string;
  iterations: number;
  is_active: number | boolean;
  password_default: number | boolean;
  avatar_path: string | null;
};

type SessionRow = QueryResultRow & {
  id: number;
  username: string;
  display_name: string | null;
  role: string;
  is_active: number | boolean;
  password_default: number | boolean;
  avatar_path: string | null;
  expires_at: string;
  revoked_at: string | null;
};

const ADMIN_CAPABILITIES = [
  "camera",
  "live",
  "dataset",
  "history",
  "mapping",
  "settings",
  "logs",
  "training",
  "user_dashboard",
  "admin.users.manage",
  "admin.roles.manage",
  "admin.devices.manage",
  "admin.bin_map.manage",
  "admin.history.read_all",
  "admin.alerts.read_all",
  "admin.model.configure",
  "admin.audio.configure",
  "admin.reports.read_all",
  "admin.collection_schedules.manage",
  "admin.device_issues.manage"
];

const USER_CAPABILITIES = [
  "user_dashboard",
  "user.bin_map.read",
  "user.alerts.read",
  "user.collection_schedule.read",
  "user.collection.mark_collected",
  "user.device_issues.create",
  "user.history.read_own",
  "user.account.manage_own"
];

const SESSION_HOURS = 12;
const PBKDF2_DIGEST = "sha256";
const TOKEN_BYTES = 32;

declare global {
  // eslint-disable-next-line no-var
  var trashSorterCloudAuthPool: Pool | undefined;
}

export class CloudAuthConfigError extends Error {
  constructor() {
    super("Cloud auth database is not configured");
    this.name = "CloudAuthConfigError";
  }
}

export function capabilitiesForRole(role: CloudAuthRole) {
  return role === "admin" ? [...ADMIN_CAPABILITIES] : [...USER_CAPABILITIES];
}

export function authDatabaseUrl() {
  return (
    process.env.TRASH_SORTER_AUTH_DATABASE_URL?.trim() ||
    process.env.DATABASE_URL?.trim() ||
    process.env.POSTGRES_URL?.trim() ||
    ""
  );
}

export function authIsConfigured() {
  return Boolean(authDatabaseUrl());
}

export function extractBearerToken(authorization: string | null) {
  const value = authorization?.trim() ?? "";
  return value.toLowerCase().startsWith("bearer ") ? value.slice(7).trim() : "";
}

export async function loginWithPassword(username: string, password: string, clientLabel = "") {
  const cleanUsername = username.trim();
  if (!cleanUsername || !password) {
    return null;
  }
  const pool = getPool();
  const account = await findAccount(cleanUsername);
  if (!account || !verifyPassword(password, account.salt, account.password_hash, Number(account.iterations))) {
    return null;
  }
  if (!isTruthy(account.is_active)) {
    return { inactive: true as const };
  }

  const now = new Date();
  const expiresAt = new Date(now.getTime() + SESSION_HOURS * 60 * 60 * 1000);
  const token = crypto.randomBytes(TOKEN_BYTES).toString("base64url");
  await pool.query(
    `insert into sessions (account_id, token_hash, created_at, expires_at, revoked_at, client_label)
     values ($1, $2, $3, $4, null, $5)`,
    [Number(account.id), tokenHash(token), iso(now), iso(expiresAt), clientLabel.trim().slice(0, 120)]
  );
  await pool.query("update accounts set last_login_at = $1, updated_at = $1 where id = $2", [
    iso(now),
    Number(account.id)
  ]);

  return {
    token,
    identity: identityFromAccount(account, iso(expiresAt))
  };
}

export async function authenticateSession(token: string) {
  if (!token) {
    return null;
  }
  const pool = getPool();
  const result = await pool.query<SessionRow>(
    `select
       accounts.id,
       accounts.username,
       accounts.display_name,
       accounts.role,
       accounts.is_active,
       accounts.password_default,
       accounts.avatar_path,
       sessions.expires_at,
       sessions.revoked_at
     from sessions
     join accounts on sessions.account_id = accounts.id
     where sessions.token_hash = $1
     limit 1`,
    [tokenHash(token)]
  );
  const row = result.rows[0];
  if (!row || row.revoked_at || !isTruthy(row.is_active) || String(row.expires_at) <= iso(new Date())) {
    return null;
  }
  return identityFromSession(row);
}

export async function revokeSession(token: string) {
  if (!token) {
    return false;
  }
  const result = await getPool().query(
    "update sessions set revoked_at = $1 where token_hash = $2 and revoked_at is null",
    [iso(new Date()), tokenHash(token)]
  );
  return (result.rowCount ?? 0) > 0;
}

export async function changePassword(accountId: number, currentPassword: string, newPassword: string, currentToken: string) {
  const pool = getPool();
  const result = await pool.query<AccountRow>("select * from accounts where id = $1 limit 1", [accountId]);
  const account = result.rows[0];
  if (!account || !verifyPassword(currentPassword, account.salt, account.password_hash, Number(account.iterations))) {
    return null;
  }
  validateNewPassword(account.username, newPassword);
  const salt = crypto.randomBytes(16);
  const iterations = Number(account.iterations) || 210_000;
  const passwordHash = pbkdf2Base64(newPassword, salt, iterations);
  const now = iso(new Date());
  await pool.query(
    `update accounts
     set password_hash = $1, salt = $2, iterations = $3, password_default = 0, updated_at = $4
     where id = $5`,
    [passwordHash, salt.toString("base64"), iterations, now, accountId]
  );
  await pool.query(
    `update sessions
     set revoked_at = $1
     where account_id = $2 and token_hash <> $3 and revoked_at is null`,
    [now, accountId, tokenHash(currentToken)]
  );
  return authenticateSession(currentToken);
}

function getPool() {
  const databaseUrl = authDatabaseUrl();
  if (!databaseUrl) {
    throw new CloudAuthConfigError();
  }
  if (!globalThis.trashSorterCloudAuthPool) {
    globalThis.trashSorterCloudAuthPool = new Pool({
      connectionString: connectionStringForPg(databaseUrl),
      max: databasePoolConcurrency(),
      ssl: shouldUseSsl(databaseUrl) ? { rejectUnauthorized: false } : undefined
    });
  }
  return globalThis.trashSorterCloudAuthPool;
}

export function cloudAuthPool() {
  return getPool();
}

async function findAccount(username: string) {
  const result = await getPool().query<AccountRow>("select * from accounts where username = $1 limit 1", [username]);
  return result.rows[0] ?? null;
}

function verifyPassword(password: string, salt: string, expectedHash: string, iterations: number) {
  const digest = pbkdf2Base64(password, Buffer.from(salt, "base64"), iterations);
  return timingSafeEqualText(digest, expectedHash);
}

function pbkdf2Base64(password: string, salt: Buffer, iterations: number) {
  return crypto.pbkdf2Sync(password, salt, iterations, 32, PBKDF2_DIGEST).toString("base64");
}

function timingSafeEqualText(left: string, right: string) {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  return leftBuffer.length === rightBuffer.length && crypto.timingSafeEqual(leftBuffer, rightBuffer);
}

function tokenHash(token: string) {
  return crypto.createHash("sha256").update(token, "utf8").digest("hex");
}

function identityFromAccount(account: AccountRow, expiresAt: string): CloudAuthIdentity {
  return {
    account_id: Number(account.id),
    role: roleFromValue(account.role),
    username: account.username,
    display_name: account.display_name ?? "",
    expires_at: expiresAt,
    password_default: isTruthy(account.password_default)
    ,avatar_path: account.avatar_path ?? ""
  };
}

function identityFromSession(row: SessionRow): CloudAuthIdentity {
  return {
    account_id: Number(row.id),
    role: roleFromValue(row.role),
    username: row.username,
    display_name: row.display_name ?? "",
    expires_at: String(row.expires_at),
    password_default: isTruthy(row.password_default)
    ,avatar_path: row.avatar_path ?? ""
  };
}

function roleFromValue(value: string): CloudAuthRole {
  return value === "admin" ? "admin" : "user";
}

function isTruthy(value: number | boolean | null | undefined) {
  return value === true || value === 1;
}

function iso(value: Date) {
  return value.toISOString().replace(".000Z", "+00:00");
}

function shouldUseSsl(databaseUrl: string) {
  try {
    const parsed = new URL(databaseUrl);
    return !["localhost", "127.0.0.1"].includes(parsed.hostname);
  } catch {
    return true;
  }
}

export function connectionStringForPg(databaseUrl: string) {
  try {
    const parsed = new URL(databaseUrl);
    parsed.searchParams.delete("sslmode");
    parsed.searchParams.delete("sslcert");
    parsed.searchParams.delete("sslkey");
    parsed.searchParams.delete("sslrootcert");
    return parsed.toString();
  } catch {
    return databaseUrl;
  }
}

function validateNewPassword(username: string, password: string) {
  if (password.length < 8) {
    throw new Error("Password must be at least 8 characters");
  }
  if (password.toLowerCase().includes(username.toLowerCase())) {
    throw new Error("Password must not contain the username");
  }
}
