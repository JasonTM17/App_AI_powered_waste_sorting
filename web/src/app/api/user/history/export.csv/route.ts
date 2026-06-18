import { NextRequest } from "next/server";

import { cleanAnalyticsRange, cloudUserHistoryCsv } from "@/lib/server/cloud-user-dashboard";
import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return handleCloudUserRequest(request, async (identity) => {
    const csv = await cloudUserHistoryCsv(identity, cleanAnalyticsRange(request.nextUrl.searchParams.get("range_days")));
    return new Response(csv, {
      headers: {
        "Content-Disposition": `attachment; filename="trash-history-${identity.username}.csv"`,
        "Content-Type": "text/csv; charset=utf-8"
      }
    });
  });
}
