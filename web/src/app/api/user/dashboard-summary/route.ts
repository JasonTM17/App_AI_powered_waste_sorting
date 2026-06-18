import { NextRequest } from "next/server";

import { cleanAnalyticsRange, cloudUserDashboardSummary } from "@/lib/server/cloud-user-dashboard";
import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const rangeDays = cleanAnalyticsRange(request.nextUrl.searchParams.get("range_days"));
  return handleCloudUserRequest(request, (identity) => cloudUserDashboardSummary(identity, rangeDays));
}
