"use client";

import { AlertTriangle, LogOut } from "lucide-react";

import { accountDisplayName, accountInitials, accountToneKey } from "@/lib/account-display";
import type { AuthMe } from "@/lib/agent";

type AccountControlProps = {
  auth: AuthMe | null;
  busy: boolean;
  onLogout: () => void;
};

export function AccountControl({ auth, busy, onLogout }: AccountControlProps) {
  const roleLabel = auth?.role === "admin" ? "Quản trị viên" : "Tài khoản người dùng";
  const displayName = accountDisplayName(auth);
  const initials = accountInitials(displayName);
  const tone = accountToneKey(auth?.username || displayName);

  return (
    <div className="account-control" aria-label={`Tài khoản đăng nhập: ${displayName}`}>
      <div className="account-chip" title={auth?.username ? `Username: ${auth.username}` : roleLabel}>
        <span className="account-avatar-frame generated-avatar" data-tone={tone} aria-hidden="true">
          <span>{initials}</span>
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
