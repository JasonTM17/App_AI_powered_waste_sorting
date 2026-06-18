import { NextRequest, NextResponse } from "next/server";

import { authenticateSession, CloudAuthConfigError, extractBearerToken, type CloudAuthIdentity } from "@/lib/server/cloud-auth";

export async function handleCloudUserRequest(
  request: NextRequest,
  operation: (identity: CloudAuthIdentity) => Promise<Response | object>
) {
  try {
    const identity = await authenticateSession(extractBearerToken(request.headers.get("authorization")));
    if (!identity) return NextResponse.json({ detail: "Invalid or missing agent token" }, { status: 401 });
    if (identity.role !== "user") return NextResponse.json({ detail: "User role required" }, { status: 403 });
    const result = await operation(identity);
    return result instanceof Response ? result : NextResponse.json(result);
  } catch (error) {
    if (error instanceof CloudAuthConfigError) return NextResponse.json({ detail: "Cloud database is not configured" }, { status: 503 });
    return NextResponse.json({ detail: "Cloud user data request failed" }, { status: 500 });
  }
}
