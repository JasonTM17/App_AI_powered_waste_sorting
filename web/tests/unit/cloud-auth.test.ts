import { describe, expect, it } from "vitest";

import { agentResponseErrorDetail } from "@/lib/agent";
import { authDatabaseUrl, capabilitiesForRole, connectionStringForPg } from "@/lib/server/cloud-auth";

describe("cloud auth", () => {
  it("falls back to the Vercel Supabase integration Postgres URL", () => {
    const previousAuthUrl = process.env.TRASH_SORTER_AUTH_DATABASE_URL;
    const previousDatabaseUrl = process.env.DATABASE_URL;
    const previousPostgresUrl = process.env.POSTGRES_URL;
    process.env.TRASH_SORTER_AUTH_DATABASE_URL = "";
    process.env.DATABASE_URL = "";
    process.env.POSTGRES_URL = "postgresql://integration.example/postgres";

    try {
      expect(authDatabaseUrl()).toBe("postgresql://integration.example/postgres");
    } finally {
      process.env.TRASH_SORTER_AUTH_DATABASE_URL = previousAuthUrl;
      process.env.DATABASE_URL = previousDatabaseUrl;
      process.env.POSTGRES_URL = previousPostgresUrl;
    }
  });

  it("strips pg SSL URL parameters so explicit SSL config is preserved", () => {
    const value = connectionStringForPg(
      "postgresql://user:pass@example.supabase.co:6543/postgres?sslmode=require&connect_timeout=10&sslrootcert=x"
    );

    const parsed = new URL(value);
    expect(parsed.searchParams.get("sslmode")).toBeNull();
    expect(parsed.searchParams.get("sslrootcert")).toBeNull();
    expect(parsed.searchParams.get("connect_timeout")).toBe("10");
  });

  it("does not grant hardware/admin capabilities to user sessions", () => {
    const userCapabilities = capabilitiesForRole("user");

    expect(userCapabilities).toContain("user_dashboard");
    expect(userCapabilities).not.toContain("camera");
    expect(userCapabilities).not.toContain("training");
    expect(userCapabilities).not.toContain("admin.users.manage");
  });

  it("summarizes HTML errors instead of leaking raw 404 pages", async () => {
    const detail = await agentResponseErrorDetail(
      new Response("<!DOCTYPE html><html><body>404</body></html>", {
        status: 404,
        headers: { "content-type": "text/html; charset=utf-8" }
      })
    );

    expect(detail).toContain("404");
    expect(detail).not.toContain("<!DOCTYPE");
    expect(detail).not.toContain("<html>");
  });
});
