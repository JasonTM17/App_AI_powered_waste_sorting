"use client";

import {
  AlertTriangle,
  Eye,
  EyeOff,
  LockKeyhole,
  LogIn,
  UserRound,
} from "lucide-react";

import { TrashSorterLogo } from "@/components/brand/trash-sorter-logo";

type AuthLoginPanelProps = {
  error: string;
  password: string;
  pending: boolean;
  sessionMessage: string;
  showPassword: boolean;
  username: string;
  onPasswordChange: (value: string) => void;
  onShowPasswordChange: (value: boolean) => void;
  onSubmit: () => void;
  onUsernameChange: (value: string) => void;
};

export function AuthLoginPanel({
  error,
  password,
  pending,
  sessionMessage,
  showPassword,
  username,
  onPasswordChange,
  onShowPasswordChange,
  onSubmit,
  onUsernameChange
}: AuthLoginPanelProps) {
  return (
    <main className="auth-screen">
      <section className="auth-panel" aria-labelledby="auth-title">
        <div className="auth-brand">
          <TrashSorterLogo variant="lockup" />
        </div>

        {sessionMessage ? (
          <div className="auth-banner" role="status">
            <AlertTriangle size={17} />
            <span>{sessionMessage}</span>
          </div>
        ) : null}

        <div className="auth-heading">
          <h1 id="auth-title">Đăng nhập hệ thống</h1>
          <p>Tài khoản xác định quyền Admin hoặc User cho dashboard phân loại rác.</p>
        </div>

        <form
          className="auth-form"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          <label className="auth-field">
            <span>Tên đăng nhập</span>
            <div className="auth-input-wrap">
              <UserRound size={18} />
              <input
                autoComplete="username"
                autoFocus
                onChange={(event) => onUsernameChange(event.target.value)}
                placeholder="admin hoặc user"
                type="text"
                value={username}
              />
            </div>
          </label>

          <label className="auth-field">
            <span>Mật khẩu</span>
            <div className={error ? "auth-input-wrap error" : "auth-input-wrap"}>
              <LockKeyhole size={18} />
              <input
                autoComplete="current-password"
                onChange={(event) => onPasswordChange(event.target.value)}
                placeholder="Nhập mật khẩu"
                type={showPassword ? "text" : "password"}
                value={password}
              />
              <button
                aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                className="auth-eye-button"
                onClick={() => onShowPasswordChange(!showPassword)}
                type="button"
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            {error ? <small role="alert">{error}</small> : null}
          </label>

          <button className="auth-submit" disabled={pending} type="submit">
            <LogIn size={18} />
            <span>{pending ? "Đang đăng nhập..." : "Đăng nhập"}</span>
          </button>
        </form>
      </section>
    </main>
  );
}
