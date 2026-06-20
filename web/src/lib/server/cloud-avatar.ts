import sharp from "sharp";
import { cloudAuthPool, type CloudAuthIdentity } from "@/lib/server/cloud-auth";

const BUCKET = "account-avatars";
export async function saveAvatar(identity: CloudAuthIdentity, file: File) {
  if (!file || file.size > 5 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(file.type)) throw new AvatarInputError("Chỉ nhận JPG, PNG hoặc WebP tối đa 5 MB");
  const bytes = await sharp(Buffer.from(await file.arrayBuffer())).rotate().resize(256, 256, { fit: "cover" }).webp({ quality: 82 }).toBuffer();
  const path = `${identity.account_id}/avatar.webp`;
  const response = await storageFetch(`/object/${BUCKET}/${path}`, { method: "POST", headers: { "Content-Type": "image/webp", "x-upsert": "true" }, body: new Uint8Array(bytes) });
  if (!response.ok) throw new Error("Không thể lưu ảnh đại diện");
  await cloudAuthPool().query("update accounts set avatar_path = $1, updated_at = $2 where id = $3", [path, new Date().toISOString(), identity.account_id]);
  return { avatar_url: await signedAvatarUrl(path) };
}
export async function deleteAvatar(identity: CloudAuthIdentity) {
  if (identity.avatar_path) await storageFetch(`/object/${BUCKET}/${identity.avatar_path}`, { method: "DELETE" });
  await cloudAuthPool().query("update accounts set avatar_path = '', updated_at = $1 where id = $2", [new Date().toISOString(), identity.account_id]);
  return { avatar_url: "" };
}
export async function signedAvatarUrl(path: string) {
  if (!path) return "";
  const response = await storageFetch(`/object/sign/${BUCKET}/${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expiresIn: 3600 }) });
  if (!response.ok) return "";
  const data = await response.json() as { signedURL?: string; signedUrl?: string };
  const signed = data.signedURL || data.signedUrl || "";
  return signed ? `${supabaseUrl()}/storage/v1${signed.startsWith("/") ? signed : `/${signed}`}` : "";
}
function storageFetch(path: string, init: RequestInit) {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY?.trim() || process.env.SUPABASE_SECRET_KEY?.trim() || "";
  if (!supabaseUrl() || !key) throw new Error("Supabase Storage chưa được cấu hình");
  const headers = new Headers(init.headers); headers.set("Authorization", `Bearer ${key}`); headers.set("apikey", key);
  return fetch(`${supabaseUrl()}/storage/v1${path}`, { ...init, headers, cache: "no-store" });
}
function supabaseUrl() { return process.env.SUPABASE_URL?.trim().replace(/\/$/, "") || ""; }
export class AvatarInputError extends Error {}
