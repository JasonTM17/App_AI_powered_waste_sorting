import { NextRequest } from "next/server";

import { cloudUserAnalytics, cleanAnalyticsRange } from "@/lib/server/cloud-user-dashboard";
import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return handleCloudUserRequest(request, (identity) => cloudUserAnalytics(identity, cleanAnalyticsRange(request.nextUrl.searchParams.get("range_days"))));
}
