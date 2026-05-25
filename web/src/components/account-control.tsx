"use client";

import { AlertTriangle, LogOut } from "lucide-react";

import type { AuthMe } from "@/lib/agent";

type AccountControlProps = {
  auth: AuthMe | null;
  busy: boolean;
  onLogout: () => void;
};

export function AccountControl({ auth, busy, onLogout }: AccountControlProps) {
  const roleLabel = auth?.role === "admin" ? "Quản trị viên" : "Tài khoản người dùng";
  const displayName = displayAccountName(auth);

  return (
    <div className="account-control" aria-label={`Tài khoản đăng nhập: ${displayName}`}>
      <div className="account-chip" title={auth?.username ? `Username: ${auth.username}` : roleLabel}>
        <span className="account-avatar-frame" aria-hidden="true">
          <img alt="" src="/brand/trash-sorter-pro-mark.png" />
        </span>
        <div>
          <strong>{displayName}</strong>
          <span>{roleLabel}</span>
        </div>
      </div>
      {auth?.password_default ? (
        <div className="account-warning" title="Đổi mật khẩu mặc định trước khi dùng production">
          <AlertTriangle size={15} />
          <span>Mật khẩu mặc định</span>
        </div>
      ) : null}
      <button className="account-logout" disabled={busy} onClick={onLogout} title="Đăng xuất" type="button">
        <LogOut size={17} />
        <span>Đăng xuất</span>
      </button>
    </div>
  );
}

function displayAccountName(auth: AuthMe | null) {
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
  return username
    .split(/[-_.\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
