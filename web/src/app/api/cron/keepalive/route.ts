import crypto from "node:crypto";

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { runDatabaseKeepalive } from "@/lib/server/keepalive";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const cronSecret = process.env.CRON_SECRET?.trim() ?? "";
  if (!cronSecret) {
    return NextResponse.json({ detail: "Cron keepalive is not configured" }, { status: 503 });
  }
  if (!matchesBearerSecret(request.headers.get("authorization"), cronSecret)) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const result = await runDatabaseKeepalive();
  const status = result.ok ? 200 : 503;
  return NextResponse.json(
    {
      ...result,
      schedule: request.headers.get("x-vercel-cron-schedule") ?? "",
      source: "vercel-cron"
    },
    { status }
  );
}

function matchesBearerSecret(authorization: string | null, expectedSecret: string) {
  const expected = Buffer.from(`Bearer ${expectedSecret}`, "utf8");
  const actual = Buffer.from(authorization ?? "", "utf8");
  return actual.length === expected.length && crypto.timingSafeEqual(actual, expected);
}
