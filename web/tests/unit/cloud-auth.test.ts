import { describe, expect, it } from "vitest";

import { agentResponseErrorDetail } from "@/lib/agent";
import { buildCloudChatResponse } from "@/lib/server/cloud-chat";
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

  it("returns a cloud chat answer without granting user hardware controls", () => {
    const response = buildCloudChatResponse("user", "Tinh trang may hom nay", Date.now());

    expect(response.available).toBe(true);
    expect(response.role).toBe("user");
    expect(response.message).toContain("Cloud");
    expect(response.message).toContain("User");
    expect(response.message).toContain("khong co quyen camera");
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
