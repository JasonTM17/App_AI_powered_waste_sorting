import { NextRequest, NextResponse } from "next/server";

import { authenticateSession, CloudAuthConfigError, extractBearerToken } from "@/lib/server/cloud-auth";
import { cloudSetDemoHardwareTarget } from "@/lib/server/cloud-operations";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  let payload: Record<string, unknown>;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body" }, { status: 400 });
  }
  try {
    const identity = await authenticateSession(extractBearerToken(request.headers.get("authorization")));
    if (!identity) return NextResponse.json({ detail: "Invalid or missing agent token" }, { status: 401 });
    if (identity.role !== "admin") return NextResponse.json({ detail: "Admin role is required" }, { status: 403 });
    const result = await cloudSetDemoHardwareTarget(identity, payload);
    if (!result) return NextResponse.json({ detail: "Station or bin not found" }, { status: 404 });
    if ("disabled" in result && result.disabled) return NextResponse.json(result, { status: 404 });
    return NextResponse.json(result);
  } catch (error) {
    if (error instanceof CloudAuthConfigError) {
      return NextResponse.json({ detail: "Cloud database is not configured" }, { status: 503 });
    }
    return NextResponse.json({ detail: "Demo bin target request failed" }, { status: 500 });
  }
}
