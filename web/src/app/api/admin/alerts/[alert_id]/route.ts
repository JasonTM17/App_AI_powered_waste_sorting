import { NextRequest, NextResponse } from "next/server";

import { authenticateSession, CloudAuthConfigError, extractBearerToken } from "@/lib/server/cloud-auth";
import { cloudAlerts, cloudPatchAlert } from "@/lib/server/cloud-operations";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function PATCH(request: NextRequest, context: { params: Promise<{ alert_id: string }> }) {
  let payload: { status?: unknown };
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid alert payload" }, { status: 400 });
  }
  const status = String(payload.status ?? "");
  if (!["open", "acknowledged", "resolved"].includes(status)) {
    return NextResponse.json({ detail: "Invalid alert status" }, { status: 400 });
  }
  try {
    const identity = await authenticateSession(extractBearerToken(request.headers.get("authorization")));
    if (!identity) return NextResponse.json({ detail: "Invalid or missing agent token" }, { status: 401 });
    if (identity.role !== "admin") return NextResponse.json({ detail: "Admin role is required" }, { status: 403 });
    const params = await context.params;
    await cloudPatchAlert(params.alert_id, status as "open" | "acknowledged" | "resolved", identity.username);
    return NextResponse.json(await cloudAlerts(identity, true));
  } catch (error) {
    if (error instanceof CloudAuthConfigError) {
      return NextResponse.json({ detail: "Cloud database is not configured" }, { status: 503 });
    }
    return NextResponse.json({ detail: "Cloud alert update failed" }, { status: 500 });
  }
}
