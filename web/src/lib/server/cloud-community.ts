import { cloudAuthPool, type CloudAuthIdentity } from "@/lib/server/cloud-auth";

const TAGS = new Set(["Thử thách tuần", "Cạnh tranh", "Mẹo xanh", "Eco Score"]);

export async function communityFeed(identity: CloudAuthIdentity, limit = 24) {
  const result = await cloudAuthPool().query(
    `select p.post_id, p.author_account_id, p.author_name, p.body, p.tag, p.repost_of, p.created_at,
            count(distinct l.account_id)::int as likes,
            count(distinct c.comment_id)::int as comments,
            count(distinct r.post_id)::int as shares,
            bool_or(l.account_id = $1) as liked_by_me,
            bool_or(r.author_account_id = $1) as shared_by_me
       from community_posts p
       left join community_likes l on l.post_id = p.post_id
       left join community_comments c on c.post_id = p.post_id and c.deleted_at is null
       left join community_posts r on r.repost_of = p.post_id and r.deleted_at is null
      where p.deleted_at is null
      group by p.post_id
      order by p.created_at desc
      limit $2`,
    [identity.account_id, Math.max(1, Math.min(50, limit))]
  );
  return { posts: result.rows.map(postDto) };
}

export async function createCommunityPost(identity: CloudAuthIdentity, input: unknown) {
  const payload = input as { body?: unknown; tag?: unknown };
  const body = clean(payload.body, 500);
  const tag = String(payload.tag ?? "Thử thách tuần");
  if (!body || !TAGS.has(tag)) throw new CommunityInputError("Nội dung hoặc chủ đề không hợp lệ");
  await rateLimit(identity.account_id, "community_posts", 10);
  await cloudAuthPool().query(
    `insert into community_posts(author_account_id, author_name, body, tag)
     values ($1, $2, $3, $4)`,
    [identity.account_id, identity.display_name || identity.username, body, tag]
  );
  return communityFeed(identity);
}

export async function setCommunityLike(identity: CloudAuthIdentity, postId: string, liked: boolean) {
  if (liked) {
    await cloudAuthPool().query(
      `insert into community_likes(post_id, account_id) values ($1::uuid, $2) on conflict do nothing`,
      [postId, identity.account_id]
    );
  } else {
    await cloudAuthPool().query(`delete from community_likes where post_id = $1::uuid and account_id = $2`, [postId, identity.account_id]);
  }
  return communityFeed(identity);
}

export async function repostCommunityPost(identity: CloudAuthIdentity, postId: string) {
  await cloudAuthPool().query(
    `insert into community_posts(author_account_id, author_name, body, tag, repost_of)
     select $2, $3, p.body, p.tag, p.post_id from community_posts p
      where p.post_id = $1::uuid and p.deleted_at is null
     on conflict (author_account_id, repost_of) do nothing`,
    [postId, identity.account_id, identity.display_name || identity.username]
  );
  return communityFeed(identity);
}

export async function communityComments(identity: CloudAuthIdentity, postId: string, body?: unknown) {
  if (body !== undefined) {
    const value = clean(body, 300);
    if (!value) throw new CommunityInputError("Bình luận không hợp lệ");
    await rateLimit(identity.account_id, "community_comments", 30);
    await cloudAuthPool().query(
      `insert into community_comments(post_id, author_account_id, author_name, body)
       values ($1::uuid, $2, $3, $4)`,
      [postId, identity.account_id, identity.display_name || identity.username, value]
    );
  }
  const result = await cloudAuthPool().query(
    `select comment_id, author_name, body, created_at from community_comments
      where post_id = $1::uuid and deleted_at is null order by created_at`, [postId]
  );
  return { comments: result.rows };
}

function postDto(row: Record<string, unknown>) {
  return { ...row, likes: Number(row.likes ?? 0), comments: Number(row.comments ?? 0), shares: Number(row.shares ?? 0), liked_by_me: Boolean(row.liked_by_me), shared_by_me: Boolean(row.shared_by_me) };
}
function clean(value: unknown, max: number) { return String(value ?? "").replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, max); }
async function rateLimit(accountId: number, table: string, max: number) {
  const column = table === "community_posts" ? "author_account_id" : "author_account_id";
  const result = await cloudAuthPool().query(`select count(*)::int as count from ${table} where ${column} = $1 and created_at > now() - interval '10 minutes'`, [accountId]);
  if (Number(result.rows[0]?.count ?? 0) >= max) throw new CommunityInputError("Bạn thao tác quá nhanh, vui lòng thử lại sau");
}
export class CommunityInputError extends Error {}
