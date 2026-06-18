import { NextRequest } from "next/server";

import { cleanAnalyticsRange, cloudUserReport } from "@/lib/server/cloud-user-dashboard";
import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return handleCloudUserRequest(request, (identity) => cloudUserReport(identity, cleanAnalyticsRange(request.nextUrl.searchParams.get("range_days"))));
}
