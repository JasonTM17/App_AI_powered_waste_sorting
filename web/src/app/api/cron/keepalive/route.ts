import crypto from "node:crypto";

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { runCloudKeepalive } from "@/lib/server/keepalive";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const ALLOWED_VERCEL_CRON_SCHEDULES = new Set(["0 3 * * 1,4"]);

export async function GET(request: NextRequest) {
  const cronSecret = process.env.CRON_SECRET?.trim() ?? "";
  const authorization = request.headers.get("authorization");
  const schedule = request.headers.get("x-vercel-cron-schedule") ?? "";

  if (authorization) {
    if (!cronSecret) {
      return NextResponse.json({ detail: "Cron keepalive is not configured" }, { status: 503 });
    }
    if (!matchesBearerSecret(authorization, cronSecret)) {
      return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
    }
  } else if (!isVercelCronRequest(request.headers)) {
    if (!cronSecret) {
      return NextResponse.json({ detail: "Cron keepalive is not configured" }, { status: 503 });
    }
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  if (!cronSecret && !isVercelCronRequest(request.headers)) {
    return NextResponse.json({ detail: "Cron keepalive is not configured" }, { status: 503 });
  }

  const result = await runCloudKeepalive();
  const status = result.ok ? 200 : 503;
  return NextResponse.json(
    {
      ...result,
      schedule,
      source: "vercel-cron"
    },
    { status }
  );
}

function isVercelCronRequest(headers: Headers) {
  const schedule = headers.get("x-vercel-cron-schedule") ?? "";
  const userAgent = headers.get("user-agent") ?? "";
  return ALLOWED_VERCEL_CRON_SCHEDULES.has(schedule) && /^vercel-cron\/1\.0\b/i.test(userAgent);
}

function matchesBearerSecret(authorization: string, expectedSecret: string) {
  const expected = Buffer.from(`Bearer ${expectedSecret}`, "utf8");
  const actual = Buffer.from(authorization, "utf8");
  return actual.length === expected.length && crypto.timingSafeEqual(actual, expected);
}
