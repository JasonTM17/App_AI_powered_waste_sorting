import { NextRequest } from "next/server";

import { proxyHardwareBridge } from "@/lib/server/hardware-bridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

async function handle(request: NextRequest, context: RouteContext) {
  const params = await context.params;
  return proxyHardwareBridge(request, params.path ?? []);
}

export async function GET(request: NextRequest, context: RouteContext) {
  return handle(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return handle(request, context);
}
