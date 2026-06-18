import { NextRequest } from "next/server";

import { cleanAnalyticsRange, cloudUserHistory } from "@/lib/server/cloud-user-dashboard";
import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const range = request.nextUrl.searchParams.get("range_days");
  return handleCloudUserRequest(request, (identity) => cloudUserHistory(identity, {
    limit: Number(request.nextUrl.searchParams.get("limit") ?? 50),
    offset: Number(request.nextUrl.searchParams.get("offset") ?? 0),
    rangeDays: range ? cleanAnalyticsRange(range) : undefined
  }));
}
