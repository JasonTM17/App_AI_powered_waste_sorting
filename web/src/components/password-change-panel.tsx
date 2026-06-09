"use client";

import { AlertTriangle, KeyRound, LogOut, ShieldCheck } from "lucide-react";

import type { AuthMe } from "@/lib/agent";

type PasswordChangePanelProps = {
  auth: AuthMe;
  busy: boolean;
  confirmPassword: string;
  currentPassword: string;
  error: string;
  newPassword: string;
  onConfirmPasswordChange: (value: string) => void;
  onCurrentPasswordChange: (value: string) => void;
  onLogout: () => void;
  onNewPasswordChange: (value: string) => void;
  onSubmit: () => void;
};

export function PasswordChangePanel({
  auth,
  busy,
  confirmPassword,
  currentPassword,
  error,
  newPassword,
  onConfirmPasswordChange,
  onCurrentPasswordChange,
  onLogout,
  onNewPasswordChange,
  onSubmit
}: PasswordChangePanelProps) {
  return (
    <main className="auth-screen">
      <section className="auth-panel password-panel" aria-labelledby="password-title">
        <div className="auth-brand">
          <div className="auth-mark">
            <ShieldCheck size={26} />
          </div>
          <div>
            <span>An toàn sản xuất</span>
            <strong>EcoSort AI</strong>
          </div>
        </div>

        <div className="auth-banner" role="status">
          <AlertTriangle size={17} />
          <span>Mật khẩu mặc định cần được đổi trước khi vào dashboard.</span>
        </div>

        <div className="auth-heading">
          <span className="eyebrow">{auth.role === "admin" ? "Tài khoản Admin" : "Tài khoản User"}</span>
          <h1 id="password-title">Đổi mật khẩu đăng nhập</h1>
          <p>Tài khoản {auth.username || "local"} sẽ tiếp tục dùng phiên hiện tại sau khi đổi mật khẩu.</p>
        </div>

        <form
          className="auth-form"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          <label className="auth-field">
            <span>Mật khẩu hiện tại</span>
            <div className="auth-input-wrap">
              <KeyRound size={18} />
              <input
                autoComplete="current-password"
                onChange={(event) => onCurrentPasswordChange(event.target.value)}
                type="password"
                value={currentPassword}
              />
            </div>
          </label>
          <label className="auth-field">
            <span>Mật khẩu mới</span>
            <div className={error ? "auth-input-wrap error" : "auth-input-wrap"}>
              <KeyRound size={18} />
              <input
                autoComplete="new-password"
                minLength={8}
                onChange={(event) => onNewPasswordChange(event.target.value)}
                type="password"
                value={newPassword}
              />
            </div>
          </label>
          <label className="auth-field">
            <span>Nhập lại mật khẩu mới</span>
            <div className={error ? "auth-input-wrap error" : "auth-input-wrap"}>
              <KeyRound size={18} />
              <input
                autoComplete="new-password"
                minLength={8}
                onChange={(event) => onConfirmPasswordChange(event.target.value)}
                type="password"
                value={confirmPassword}
              />
            </div>
            {error ? <small role="alert">{error}</small> : null}
          </label>

          <button className="auth-submit" disabled={busy} type="submit">
            <KeyRound size={18} />
            <span>{busy ? "Đang đổi mật khẩu..." : "Đổi mật khẩu"}</span>
          </button>
          <button className="secondary-button full-button" disabled={busy} onClick={onLogout} type="button">
            <LogOut size={17} />
            <span>Đăng xuất</span>
          </button>
        </form>
      </section>
    </main>
  );
}
