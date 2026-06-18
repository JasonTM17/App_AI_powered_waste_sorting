import { NextRequest, NextResponse } from "next/server";

import { authenticateSession, CloudAuthConfigError, extractBearerToken } from "@/lib/server/cloud-auth";
import { cloudCompleteCollection } from "@/lib/server/cloud-operations";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest, context: { params: Promise<{ schedule_id: string }> }) {
  let payload: { note?: unknown };
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid collection payload" }, { status: 400 });
  }
  try {
    const identity = await authenticateSession(extractBearerToken(request.headers.get("authorization")));
    if (!identity) return NextResponse.json({ detail: "Invalid or missing agent token" }, { status: 401 });
    const params = await context.params;
    const schedule = await cloudCompleteCollection(identity, params.schedule_id, String(payload.note ?? ""));
    if (!schedule) return NextResponse.json({ detail: "Collection schedule not found" }, { status: 404 });
    return NextResponse.json({ ok: true, schedule, already_completed: false, message: "Collection marked complete" });
  } catch (error) {
    if (error instanceof CloudAuthConfigError) {
      return NextResponse.json({ detail: "Cloud database is not configured" }, { status: 503 });
    }
    return NextResponse.json({ detail: "Cloud collection update failed" }, { status: 500 });
  }
}
