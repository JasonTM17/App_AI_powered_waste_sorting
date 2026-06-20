import { NextRequest, NextResponse } from "next/server";

import { authenticateSession, CloudAuthConfigError, extractBearerToken } from "@/lib/server/cloud-auth";

type BridgeRoute = {
  path: string;
  methods: ReadonlySet<string>;
};

const ALLOWED_ROUTES: BridgeRoute[] = [
  route("/api/status", ["GET"]),
  route("/api/camera/start", ["POST"]),
  route("/api/camera/stop", ["POST"]),
  route("/api/camera/stream-token", ["POST"]),
  route("/api/live", ["GET"]),
  route("/api/training/status", ["GET"]),
  route("/api/settings", ["GET"]),
  route("/api/model/classes", ["GET"]),
  route("/api/common-waste/catalog", ["GET"]),
  route("/api/hardware/profile", ["GET"]),
  route("/api/hardware/diagnostics", ["GET"]),
  route("/api/dataset/camera-sample", ["POST"]),
  route("/api/dataset/capture-session", ["GET"]),
  route("/api/dataset/capture-session/start", ["POST"]),
  route("/api/dataset/capture-session/capture", ["POST"]),
  route("/api/dataset/capture-session/stop", ["POST"]),
  route("/api/learn-now/status", ["GET"]),
  route("/api/learn-now/refresh-references", ["POST"]),
  route("/api/learn-now/unknown/capture", ["POST"]),
  route("/api/learn-now/micro-train/start", ["POST"])
];

const DEFAULT_TIMEOUT_MS = 45_000;

export async function proxyHardwareBridge(request: NextRequest, segments: string[]) {
  try {
    const identity = await authenticateSession(extractBearerToken(request.headers.get("authorization")));
    if (!identity) {
      return NextResponse.json({ detail: "Invalid or missing agent token" }, { status: 401 });
    }
    if (identity.role !== "admin" || identity.password_default) {
      return NextResponse.json({ detail: "Admin role is required" }, { status: 403 });
    }

    const targetPath = `/api/${segments.map(encodeURIComponent).join("/")}`;
    if (!isAllowed(targetPath, request.method)) {
      return NextResponse.json({ detail: "Hardware bridge route is not allowed" }, { status: 404 });
    }

    const bridgeUrl = hardwareBridgeUrl();
    const bridgeSecret = hardwareBridgeSecret();
    if (!bridgeUrl || !bridgeSecret) {
      return NextResponse.json({ detail: "Hardware bridge is not configured" }, { status: 503 });
    }

    const targetUrl = new URL(targetPath, `${bridgeUrl}/`);
    request.nextUrl.searchParams.forEach((value, key) => {
      targetUrl.searchParams.append(key, value);
    });

    const response = await forwardToBridge(request, targetUrl, bridgeSecret);
    const payload = await response.text();
    const contentType = response.headers.get("content-type") || "application/json";

    if (!response.ok) {
      return responseFromBridge(payload, contentType, response.status);
    }

    if (targetPath === "/api/camera/stream-token") {
      return streamTokenResponse(payload, contentType, bridgeUrl, response.status);
    }
    return responseFromBridge(payload, contentType, response.status);
  } catch (error) {
    if (error instanceof CloudAuthConfigError) {
      return NextResponse.json({ detail: "Cloud database is not configured" }, { status: 503 });
    }
    const aborted = error instanceof DOMException && error.name === "AbortError";
    return NextResponse.json(
      { detail: aborted ? "Hardware bridge timed out" : "Hardware bridge request failed" },
      { status: 502 }
    );
  }
}

function route(path: string, methods: string[]): BridgeRoute {
  return { path, methods: new Set(methods.map((method) => method.toUpperCase())) };
}

function isAllowed(path: string, method: string) {
  return ALLOWED_ROUTES.some((item) => item.path === path && item.methods.has(method.toUpperCase()));
}

function hardwareBridgeUrl() {
  const raw = process.env.TRASH_SORTER_HARDWARE_BRIDGE_URL?.trim().replace(/\/$/, "") ?? "";
  if (!raw) {
    return "";
  }
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:" && url.protocol !== "http:") {
      return "";
    }
    return url.toString().replace(/\/$/, "");
  } catch {
    return "";
  }
}

function hardwareBridgeSecret() {
  return process.env.TRASH_SORTER_HARDWARE_BRIDGE_SECRET?.trim() ?? "";
}

async function forwardToBridge(request: NextRequest, targetUrl: URL, bridgeSecret: string) {
  const headers = new Headers();
  headers.set("Authorization", request.headers.get("authorization") ?? "");
  headers.set("X-Hardware-Bridge-Secret", bridgeSecret);
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("Content-Type", contentType);
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  try {
    const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.text();
    return await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: controller.signal
    });
  } finally {
    clearTimeout(timer);
  }
}

function responseFromBridge(payload: string, contentType: string, status: number) {
  if (contentType.includes("application/json")) {
    try {
      return NextResponse.json(JSON.parse(payload), { status });
    } catch {
      return NextResponse.json({ detail: payload || "Hardware bridge returned invalid JSON" }, { status });
    }
  }
  return new NextResponse(payload, { status, headers: { "content-type": contentType } });
}

function streamTokenResponse(payload: string, contentType: string, bridgeUrl: string, status: number) {
  if (!contentType.includes("application/json")) {
    return responseFromBridge(payload, contentType, status);
  }
  const data = JSON.parse(payload) as { token?: string; expires_at?: string };
  if (!data.token) {
    return NextResponse.json(data, { status });
  }
  const streamUrl = new URL("/api/camera/stream", `${bridgeUrl}/`);
  streamUrl.searchParams.set("stream_token", data.token);
  return NextResponse.json({ ...data, stream_url: streamUrl.toString() }, { status });
}
