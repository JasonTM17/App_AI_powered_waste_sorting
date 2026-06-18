import { NextRequest, NextResponse } from "next/server";

import { CloudAuthConfigError, extractBearerToken, revokeSession } from "@/lib/server/cloud-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    await revokeSession(extractBearerToken(request.headers.get("authorization")));
    return NextResponse.json({ message: "Da dang xuat" });
  } catch (error) {
    if (error instanceof CloudAuthConfigError) {
      return NextResponse.json({ detail: "Account login is not configured" }, { status: 503 });
    }
    return NextResponse.json({ detail: "Cloud auth logout failed" }, { status: 500 });
  }
}
