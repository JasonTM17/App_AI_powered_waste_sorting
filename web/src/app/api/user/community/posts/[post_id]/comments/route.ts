import { NextRequest, NextResponse } from "next/server";
import { communityComments, CommunityInputError } from "@/lib/server/cloud-community";
import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";
export const runtime = "nodejs"; export const dynamic = "force-dynamic";
type Context = { params: Promise<{ post_id: string }> };
export async function GET(request: NextRequest, context: Context) { const { post_id } = await context.params; return handleCloudUserRequest(request, (identity) => communityComments(identity, post_id)); }
export async function POST(request: NextRequest, context: Context) {
  const { post_id } = await context.params;
  return handleCloudUserRequest(request, async (identity) => {
    try { const payload = await request.json(); return await communityComments(identity, post_id, payload.body); }
    catch (error) { if (error instanceof CommunityInputError) return NextResponse.json({ detail: error.message }, { status: 400 }); throw error; }
  });
}
