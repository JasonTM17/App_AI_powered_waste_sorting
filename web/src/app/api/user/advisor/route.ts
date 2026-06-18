import { NextRequest } from "next/server";

import { cleanAnalyticsRange, cloudUserAdvisor } from "@/lib/server/cloud-user-dashboard";
import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  let rangeDays = cleanAnalyticsRange(null);
  try {
    const payload = await request.json();
    rangeDays = cleanAnalyticsRange(String(payload?.range_days ?? "30"));
  } catch {
    return new Response(JSON.stringify({ detail: "Invalid advisor payload" }), {
      status: 400,
      headers: { "Content-Type": "application/json" }
    });
  }
  return handleCloudUserRequest(request, (identity) => cloudUserAdvisor(identity, rangeDays));
}
