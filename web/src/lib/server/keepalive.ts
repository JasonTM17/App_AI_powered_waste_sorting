import { Client } from "pg";

import { connectionStringForPg } from "@/lib/server/cloud-auth";

type KeepaliveEnvironment = NodeJS.ProcessEnv;

export type KeepaliveTarget = {
  databaseUrl: string;
  name: string;
};

export type KeepaliveTargetResult = {
  name: string;
  ok: boolean;
  touched_at?: string;
};

type RunKeepaliveOptions = {
  env?: KeepaliveEnvironment;
  touch?: (target: KeepaliveTarget, env: KeepaliveEnvironment) => Promise<string>;
};

export function configuredKeepaliveTargets(env: KeepaliveEnvironment = process.env): KeepaliveTarget[] {
  const candidates = [
    ["auth", env.TRASH_SORTER_AUTH_DATABASE_URL?.trim() || env.DATABASE_URL?.trim() || env.POSTGRES_URL?.trim()],
    ["supabase", env.TRASH_SORTER_SUPABASE_DATABASE_URL?.trim()]
  ] as const;
  const targets = new Map<string, { databaseUrl: string; names: string[] }>();

  for (const [name, databaseUrl] of candidates) {
    if (!databaseUrl) continue;
    const existing = targets.get(databaseUrl);
    if (existing) {
      existing.names.push(name);
    } else {
      targets.set(databaseUrl, { databaseUrl, names: [name] });
    }
  }

  return [...targets.values()].map(({ databaseUrl, names }) => ({
    databaseUrl,
    name: names.sort().join("+")
  }));
}

export async function runDatabaseKeepalive(options: RunKeepaliveOptions = {}) {
  const env = options.env ?? process.env;
  const targets = configuredKeepaliveTargets(env);
  const touch = options.touch ?? touchDatabase;
  const results: KeepaliveTargetResult[] = [];

  for (const target of targets) {
    try {
      results.push({
        name: target.name,
        ok: true,
        touched_at: await touch(target, env)
      });
    } catch {
      results.push({ name: target.name, ok: false });
    }
  }

  return {
    configured: targets.length > 0,
    ok: targets.length > 0 && results.every((result) => result.ok),
    targets: results
  };
}

async function touchDatabase(target: KeepaliveTarget, env: KeepaliveEnvironment) {
  const timeoutMs = positiveInteger(env.TRASH_SORTER_DB_STATEMENT_TIMEOUT_MS, 15_000);
  const client = new Client({
    connectionString: connectionStringForPg(target.databaseUrl),
    connectionTimeoutMillis: Math.min(timeoutMs, 10_000),
    query_timeout: timeoutMs,
    ssl: shouldUseSsl(target.databaseUrl) ? { rejectUnauthorized: false } : undefined
  });

  try {
    await client.connect();
    await client.query(`set statement_timeout = ${timeoutMs}`);
    const result = await client.query<{ touched_at: Date | string }>(
      "select current_timestamp as touched_at"
    );
    const touchedAt = result.rows[0]?.touched_at;
    return touchedAt instanceof Date ? touchedAt.toISOString() : String(touchedAt ?? new Date().toISOString());
  } finally {
    await client.end().catch(() => undefined);
  }
}

function positiveInteger(raw: string | undefined, fallback: number) {
  const parsed = Number.parseInt(raw ?? "", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function shouldUseSsl(databaseUrl: string) {
  try {
    return !["localhost", "127.0.0.1"].includes(new URL(databaseUrl).hostname);
  } catch {
    return true;
  }
}
