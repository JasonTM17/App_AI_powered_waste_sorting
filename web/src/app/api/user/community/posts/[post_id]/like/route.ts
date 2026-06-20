import { NextRequest } from "next/server";
import { setCommunityLike } from "@/lib/server/cloud-community";
import { handleCloudUserRequest } from "@/lib/server/cloud-user-route";
export const runtime = "nodejs"; export const dynamic = "force-dynamic";
type Context = { params: Promise<{ post_id: string }> };
export async function POST(request: NextRequest, context: Context) { const { post_id } = await context.params; return handleCloudUserRequest(request, (identity) => setCommunityLike(identity, post_id, true)); }
export async function DELETE(request: NextRequest, context: Context) { const { post_id } = await context.params; return handleCloudUserRequest(request, (identity) => setCommunityLike(identity, post_id, false)); }
