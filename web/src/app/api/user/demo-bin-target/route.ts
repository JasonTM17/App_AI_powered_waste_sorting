import { NextRequest, NextResponse } from "next/server";

import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  return handleCloudUserRequest(request, async () =>
    NextResponse.json(
      { detail: "Only an Admin can assign the shared hardware sensor to a map bin." },
      { status: 403 }
    )
  );
}
