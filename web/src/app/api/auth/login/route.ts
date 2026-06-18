import { NextRequest, NextResponse } from "next/server";

import {
  capabilitiesForRole,
  CloudAuthConfigError,
  loginWithPassword
} from "@/lib/server/cloud-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  let payload: { username?: unknown; password?: unknown };
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid login payload" }, { status: 400 });
  }

  try {
    const result = await loginWithPassword(
      String(payload.username ?? ""),
      String(payload.password ?? ""),
      request.headers.get("user-agent") ?? "vercel-web"
    );
    if (!result) {
      return NextResponse.json({ detail: "Invalid username or password" }, { status: 401 });
    }
    if ("inactive" in result) {
      return NextResponse.json({ detail: "Account is disabled" }, { status: 403 });
    }
    const { identity, token } = result;
    return NextResponse.json({
      token,
      role: identity.role,
      account_id: identity.account_id,
      username: identity.username,
      display_name: identity.display_name,
      capabilities: capabilitiesForRole(identity.role),
      expires_at: identity.expires_at,
      password_default: identity.password_default
    });
  } catch (error) {
    if (error instanceof CloudAuthConfigError) {
      return NextResponse.json({ detail: "Account login is not configured" }, { status: 503 });
    }
    return NextResponse.json({ detail: "Cloud auth login failed" }, { status: 500 });
  }
}
