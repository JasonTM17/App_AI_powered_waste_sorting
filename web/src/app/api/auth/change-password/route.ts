import { NextRequest, NextResponse } from "next/server";

import {
  authenticateSession,
  capabilitiesForRole,
  changePassword,
  CloudAuthConfigError,
  extractBearerToken
} from "@/lib/server/cloud-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const token = extractBearerToken(request.headers.get("authorization"));
  let payload: { current_password?: unknown; new_password?: unknown };
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid password payload" }, { status: 400 });
  }

  try {
    const current = await authenticateSession(token);
    if (!current) {
      return NextResponse.json({ detail: "Invalid or missing agent token" }, { status: 401 });
    }
    const updated = await changePassword(
      current.account_id,
      String(payload.current_password ?? ""),
      String(payload.new_password ?? ""),
      token
    );
    if (!updated) {
      return NextResponse.json({ detail: "Current password is invalid" }, { status: 401 });
    }
    return NextResponse.json({
      role: updated.role,
      capabilities: capabilitiesForRole(updated.role),
      auth_required: true,
      account_id: updated.account_id,
      username: updated.username,
      display_name: updated.display_name,
      token_source: "session",
      session_expires_at: updated.expires_at,
      password_default: updated.password_default
    });
  } catch (error) {
    if (error instanceof CloudAuthConfigError) {
      return NextResponse.json({ detail: "Account login is not configured" }, { status: 503 });
    }
    if (error instanceof Error) {
      return NextResponse.json({ detail: error.message }, { status: 400 });
    }
    return NextResponse.json({ detail: "Cloud auth password change failed" }, { status: 500 });
  }
}
