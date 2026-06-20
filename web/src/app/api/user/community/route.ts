import { NextRequest, NextResponse } from "next/server";
import { communityFeed, CommunityInputError, createCommunityPost } from "@/lib/server/cloud-community";
import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";
export const runtime = "nodejs"; export const dynamic = "force-dynamic";
export async function GET(request: NextRequest) { return handleCloudUserRequest(request, (identity) => communityFeed(identity, Number(request.nextUrl.searchParams.get("limit") ?? 24))); }
export async function POST(request: NextRequest) {
  return handleCloudUserRequest(request, async (identity) => {
    try { return await createCommunityPost(identity, await request.json()); }
    catch (error) { if (error instanceof CommunityInputError) return NextResponse.json({ detail: error.message }, { status: 400 }); throw error; }
  });
}
