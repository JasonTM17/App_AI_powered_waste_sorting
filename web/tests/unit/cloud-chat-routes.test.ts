import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({ authenticate: vi.fn(), generate: vi.fn() }));

vi.mock("@/lib/server/cloud-auth", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/server/cloud-auth")>()),
  authenticateSession: mocks.authenticate
}));
vi.mock("@/lib/server/cloud-chat", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/server/cloud-chat")>()),
  generateCloudChatResponse: mocks.generate
}));

import type { CloudAuthIdentity } from "@/lib/server/cloud-auth";
import { CloudChatInputError } from "@/lib/server/cloud-chat";
import { POST as adminPost } from "@/app/api/admin/chat/route";
import { POST as userPost } from "@/app/api/user/chat/route";

const USER: CloudAuthIdentity = {
  account_id: 7,
  role: "user",
  username: "alice",
  display_name: "Alice",
  expires_at: "2026-07-01T00:00:00Z",
  password_default: false
};

function request(body: unknown) {
  return new NextRequest("http://localhost/api/user/chat", {
    method: "POST",
    headers: { Authorization: "Bearer session", "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

describe("cloud chat routes", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.authenticate.mockResolvedValue(USER);
    mocks.generate.mockResolvedValue({ available: true, message: "Xin chào" });
  });

  it("rejects unauthenticated requests", async () => {
    mocks.authenticate.mockResolvedValue(null);
    expect((await userPost(request({ message: "Xin chào" }))).status).toBe(401);
  });

  it("keeps User out of the Admin endpoint", async () => {
    expect((await adminPost(request({ message: "Trạng thái camera" }))).status).toBe(403);
    expect(mocks.generate).not.toHaveBeenCalled();
  });

  it("maps validated input failures to HTTP 400", async () => {
    mocks.generate.mockRejectedValue(new CloudChatInputError("Vui lòng nhập câu hỏi."));
    const response = await userPost(request({ message: "" }));
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ detail: "Vui lòng nhập câu hỏi." });
  });

  it("passes the authenticated identity and raw message to the chat service", async () => {
    const response = await userPost(request({ message: "Hôm nay bạn thế nào?" }));
    expect(response.status).toBe(200);
    expect(mocks.generate).toHaveBeenCalledWith(USER, "Hôm nay bạn thế nào?", expect.any(Number));
  });
});
