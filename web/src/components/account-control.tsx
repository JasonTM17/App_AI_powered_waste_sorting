"use client";

import { AlertTriangle, LogOut, ShieldCheck, UserRound } from "lucide-react";

import type { AuthMe } from "@/lib/agent";

type AccountControlProps = {
  auth: AuthMe | null;
  busy: boolean;
  onLogout: () => void;
};

export function AccountControl({ auth, busy, onLogout }: AccountControlProps) {
  const roleLabel = auth?.role === "admin" ? "Quản trị viên" : "Người dùng";
  const Icon = auth?.role === "admin" ? ShieldCheck : UserRound;

  return (
    <div className="account-control" aria-label="Tài khoản đăng nhập">
      <div className="account-chip">
        <Icon size={17} />
        <div>
          <strong>{auth?.username || roleLabel}</strong>
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
