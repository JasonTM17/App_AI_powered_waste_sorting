import { describe, expect, it } from "vitest";

import { capabilitiesForRole, connectionStringForPg } from "@/lib/server/cloud-auth";

describe("cloud auth", () => {
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
});
