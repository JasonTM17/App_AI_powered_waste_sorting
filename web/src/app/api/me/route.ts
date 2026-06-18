import { NextRequest, NextResponse } from "next/server";

import {
  authenticateSession,
  capabilitiesForRole,
  CloudAuthConfigError,
  extractBearerToken
} from "@/lib/server/cloud-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const identity = await authenticateSession(extractBearerToken(request.headers.get("authorization")));
    if (!identity) {
      return NextResponse.json({ detail: "Invalid or missing agent token" }, { status: 401 });
    }
    return NextResponse.json({
      role: identity.role,
      capabilities: capabilitiesForRole(identity.role),
      auth_required: true,
      account_id: identity.account_id,
      username: identity.username,
      display_name: identity.display_name,
      token_source: "session",
      session_expires_at: identity.expires_at,
      password_default: identity.password_default
    });
  } catch (error) {
    if (error instanceof CloudAuthConfigError) {
      return NextResponse.json({ detail: "Account login is not configured" }, { status: 503 });
    }
    return NextResponse.json({ detail: "Cloud auth session check failed" }, { status: 500 });
  }
}
