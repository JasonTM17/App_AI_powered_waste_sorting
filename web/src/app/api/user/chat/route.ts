import { NextRequest, NextResponse } from "next/server";

import {
  authenticateSession,
  CloudAuthConfigError,
  extractBearerToken
} from "@/lib/server/cloud-auth";
import { CloudChatInputError, generateCloudChatResponse } from "@/lib/server/cloud-chat";

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
    const identity = await authenticateSession(extractBearerToken(request.headers.get("authorization")));
    if (!identity) {
      return NextResponse.json({ detail: "Invalid or missing agent token" }, { status: 401 });
    }
    if (identity.role !== "user") {
      return NextResponse.json({ detail: "User role required" }, { status: 403 });
    }
    return NextResponse.json(await generateCloudChatResponse(identity, payload.message, startedAt));
  } catch (error) {
    if (error instanceof CloudChatInputError) {
      return NextResponse.json({ detail: error.message }, { status: 400 });
    }
    if (error instanceof CloudAuthConfigError) {
      return NextResponse.json({ detail: "Account login is not configured" }, { status: 503 });
    }
    return NextResponse.json({ detail: "Cloud user chat failed" }, { status: 500 });
  }
}
