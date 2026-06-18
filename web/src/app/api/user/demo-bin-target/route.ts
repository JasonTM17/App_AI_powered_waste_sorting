import { NextRequest, NextResponse } from "next/server";

import { cloudSetDemoHardwareTarget } from "@/lib/server/cloud-operations";
import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  let payload: Record<string, unknown>;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body" }, { status: 400 });
  }
  return handleCloudUserRequest(request, async (identity) => {
    const result = await cloudSetDemoHardwareTarget(identity, payload);
    if (!result) return NextResponse.json({ detail: "Station or bin is outside this User scope" }, { status: 404 });
    if ("disabled" in result && result.disabled) return NextResponse.json(result, { status: 404 });
    return result;
  });
}
