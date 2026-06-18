import { NextRequest, NextResponse } from "next/server";

import { authenticateSession, CloudAuthConfigError, extractBearerToken } from "@/lib/server/cloud-auth";
import { cloudAlerts } from "@/lib/server/cloud-operations";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const identity = await authenticateSession(extractBearerToken(request.headers.get("authorization")));
    if (!identity) return NextResponse.json({ detail: "Invalid or missing agent token" }, { status: 401 });
    if (identity.role !== "admin") return NextResponse.json({ detail: "Admin role is required" }, { status: 403 });
    const includeResolved = request.nextUrl.searchParams.get("include_resolved") !== "false";
    return NextResponse.json(await cloudAlerts(identity, includeResolved));
  } catch (error) {
    console.error("cloud admin alerts failed", error);
    if (error instanceof CloudAuthConfigError) {
      return NextResponse.json({ detail: "Cloud database is not configured" }, { status: 503 });
    }
    return NextResponse.json({ detail: "Cloud alerts failed" }, { status: 500 });
  }
}
