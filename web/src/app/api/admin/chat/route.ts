import { NextRequest, NextResponse } from "next/server";

import {
  authenticateSession,
  CloudAuthConfigError,
  extractBearerToken
} from "@/lib/server/cloud-auth";
import { CloudChatInputError, createCloudChatStreamResponse } from "@/lib/server/cloud-chat";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const startedAt = Date.now();
  let payload: { message?: unknown };
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid chat payload" }, { status: 400 });
  }

  try {
    const authStartedAt = Date.now();
    const identity = await authenticateSession(extractBearerToken(request.headers.get("authorization")));
    if (!identity) {
      return NextResponse.json({ detail: "Invalid or missing agent token" }, { status: 401 });
    }
    if (identity.role !== "admin") {
      return NextResponse.json({ detail: "Admin role is required" }, { status: 403 });
    }
    const response = await createCloudChatStreamResponse(identity, payload.message, startedAt, request.signal);
    response.headers.set(
      "Server-Timing",
      `auth;dur=${Date.now() - authStartedAt}, ${response.headers.get("Server-Timing") ?? ""}`
    );
    return response;
  } catch (error) {
    if (error instanceof CloudChatInputError) {
      return NextResponse.json({ detail: error.message }, { status: 400 });
    }
    if (error instanceof CloudAuthConfigError) {
      return NextResponse.json({ detail: "Account login is not configured" }, { status: 503 });
    }
    return NextResponse.json({ detail: "Cloud admin chat failed" }, { status: 500 });
  }
}
