import { NextRequest } from "next/server";
import { repostCommunityPost } from "@/lib/server/cloud-community";
import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";
export const runtime = "nodejs"; export const dynamic = "force-dynamic";
export async function POST(request: NextRequest, context: { params: Promise<{ post_id: string }> }) { const { post_id } = await context.params; return handleCloudUserRequest(request, (identity) => repostCommunityPost(identity, post_id)); }
