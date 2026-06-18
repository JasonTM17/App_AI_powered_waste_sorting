import { NextRequest } from "next/server";

import { cloudUserDevice } from "@/lib/server/cloud-user-dashboard";
import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return handleCloudUserRequest(request, cloudUserDevice);
}
