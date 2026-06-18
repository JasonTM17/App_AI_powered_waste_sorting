import { NextRequest, NextResponse } from "next/server";

import { authenticateSession, CloudAuthConfigError, extractBearerToken } from "@/lib/server/cloud-auth";
import { cloudCreateDeviceIssue } from "@/lib/server/cloud-operations";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  let payload: Record<string, unknown>;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid issue payload" }, { status: 400 });
  }
  try {
    const identity = await authenticateSession(extractBearerToken(request.headers.get("authorization")));
    if (!identity) return NextResponse.json({ detail: "Invalid or missing agent token" }, { status: 401 });
    const issue = await cloudCreateDeviceIssue(identity, payload);
    if (!issue) return NextResponse.json({ detail: "Bin station not found" }, { status: 404 });
    return NextResponse.json(issue);
  } catch (error) {
    if (error instanceof CloudAuthConfigError) {
      return NextResponse.json({ detail: "Cloud database is not configured" }, { status: 503 });
    }
    return NextResponse.json({ detail: "Cloud issue report failed" }, { status: 500 });
  }
}
