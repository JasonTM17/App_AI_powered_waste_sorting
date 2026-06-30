import { describe, expect, it } from "vitest";
import {
  configuredKeepaliveTargets,
  runCloudKeepalive
} from "@/lib/server/keepalive";

describe("database keepalive", () => {
  it("deduplicates one database used for auth and Supabase", () => {
    const env = {
      TRASH_SORTER_AUTH_DATABASE_URL: "postgresql://same",
      TRASH_SORTER_SUPABASE_DATABASE_URL: "postgresql://same"
    } as NodeJS.ProcessEnv;

    expect(configuredKeepaliveTargets(env)).toEqual([
      { databaseUrl: "postgresql://same", name: "auth+supabase" }
    ]);
  });

  it("touches configured databases sequentially", async () => {
    const events: string[] = [];
    const env = {
      TRASH_SORTER_AUTH_DATABASE_URL: "postgresql://auth",
      TRASH_SORTER_SUPABASE_DATABASE_URL: "postgresql://supabase"
    } as NodeJS.ProcessEnv;

    const result = await runCloudKeepalive({
      env,
      touch: async (target) => {
        events.push(`start:${target.name}`);
        await Promise.resolve();
        events.push(`end:${target.name}`);
        return "2026-06-30T03:00:00.000Z";
      }
    });

    expect(events).toEqual(["start:auth", "end:auth", "start:supabase", "end:supabase"]);
    expect(result).toMatchObject({
      configured: true,
      ok: true,
      targets: [{ name: "auth", ok: true }, { name: "supabase", ok: true }]
    });
  });

  it("reports an unconfigured database without pretending success", async () => {
    await expect(runCloudKeepalive({ env: {} })).resolves.toEqual({
      configured: false,
      ok: false,
      targets: []
    });
  });

  it("touches Supabase PostgREST after the database queue", async () => {
    const events: string[] = [];
    const env = {
      TRASH_SORTER_AUTH_DATABASE_URL: "postgresql://auth",
      SUPABASE_URL: "https://project.supabase.co",
      SUPABASE_SERVICE_ROLE_KEY: "test-service-key"
    } as NodeJS.ProcessEnv;

    const result = await runCloudKeepalive({
      env,
      touch: async () => {
        events.push("database");
        return "2026-06-30T03:00:00.000Z";
      },
      touchSupabase: async () => {
        events.push("supabase-api");
        return "2026-06-30T03:00:01.000Z";
      }
    });

    expect(events).toEqual(["database", "supabase-api"]);
    expect(result.targets).toEqual([
      { name: "auth", ok: true, touched_at: "2026-06-30T03:00:00.000Z" },
      { name: "supabase-api", ok: true, touched_at: "2026-06-30T03:00:01.000Z" }
    ]);
  });
});
