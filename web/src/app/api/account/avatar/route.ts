import { NextRequest, NextResponse } from "next/server";
import { authenticateSession, CloudAuthConfigError, extractBearerToken } from "@/lib/server/cloud-auth";
import { AvatarInputError, deleteAvatar, saveAvatar } from "@/lib/server/cloud-avatar";
export const runtime = "nodejs"; export const dynamic = "force-dynamic";
async function identity(request: NextRequest) { return authenticateSession(extractBearerToken(request.headers.get("authorization"))); }
export async function POST(request: NextRequest) {
  try { const auth = await identity(request); if (!auth) return NextResponse.json({ detail: "Invalid session" }, { status: 401 }); const form = await request.formData(); return NextResponse.json(await saveAvatar(auth, form.get("avatar") as File)); }
  catch (error) { if (error instanceof AvatarInputError) return NextResponse.json({ detail: error.message }, { status: 400 }); if (error instanceof CloudAuthConfigError) return NextResponse.json({ detail: "Cloud database is not configured" }, { status: 503 }); return NextResponse.json({ detail: error instanceof Error ? error.message : "Avatar upload failed" }, { status: 500 }); }
}
export async function DELETE(request: NextRequest) { try { const auth = await identity(request); if (!auth) return NextResponse.json({ detail: "Invalid session" }, { status: 401 }); return NextResponse.json(await deleteAvatar(auth)); } catch { return NextResponse.json({ detail: "Avatar delete failed" }, { status: 500 }); } }
