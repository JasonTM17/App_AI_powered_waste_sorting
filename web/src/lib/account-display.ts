import type { AuthMe } from "@/lib/agent";

const MEMBER_DISPLAY_NAMES: Record<string, string> = {
  "nguyen-son": "Nguyễn Sơn",
  "ngoc-quyen": "Ngọc Quyên",
  "gia-kiet": "Gia Kiệt",
  "minh-huy": "Minh Huy",
  "hong-thuy": "Hồng Thủy"
};

const ACCOUNT_TONES = ["leaf", "mint", "sky", "amber", "rose", "violet"] as const;

export function accountDisplayName(auth: Pick<AuthMe, "display_name" | "role" | "username"> | null): string {
  const explicit = auth?.display_name?.trim();
  if (explicit) {
    return explicit;
  }
  const username = auth?.username?.trim();
  if (!username) {
    return auth?.role === "admin" ? "Quản trị EcoSort" : "Thành viên EcoSort";
  }
  const normalized = username.toLowerCase();
  if (auth?.role === "admin" && normalized === "admin") {
    return "Quản trị EcoSort";
  }
  if (auth?.role === "user" && normalized === "user") {
    return "Thành viên EcoSort";
  }
  if (MEMBER_DISPLAY_NAMES[normalized]) {
    return MEMBER_DISPLAY_NAMES[normalized];
  }
  return username
    .split(/[-_.\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function accountInitials(name: string): string {
  const parts = name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) {
    return "EC";
  }
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return `${parts[0][0] ?? ""}${parts[parts.length - 1][0] ?? ""}`.toUpperCase();
}

export function accountToneKey(seed: string): (typeof ACCOUNT_TONES)[number] {
  let hash = 0;
  for (const char of seed || "ecosort") {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  }
  return ACCOUNT_TONES[hash % ACCOUNT_TONES.length];
}
