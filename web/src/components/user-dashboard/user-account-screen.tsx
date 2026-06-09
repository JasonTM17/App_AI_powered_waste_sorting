"use client";

import { UserRound } from "lucide-react";

import type { UserDashboardPanelProps } from "./user-dashboard-types";

export function UserAccountScreen(props: UserDashboardPanelProps) {
  return (
    <section className="user-panel user-account-panel">
      <div className="user-panel-heading inline">
        <div>
          <span className="eyebrow">Tài khoản</span>
          <strong>{props.auth?.username || "User"}</strong>
        </div>
        <UserRound size={21} />
      </div>
      <div className="account-form-grid">
        <label>
          Mật khẩu hiện tại
          <input
            type="password"
            value={props.passwordCurrent}
            onChange={(event) => props.onPasswordCurrentChange(event.target.value)}
          />
        </label>
        <label>
          Mật khẩu mới
          <input
            type="password"
            value={props.passwordNew}
            onChange={(event) => props.onPasswordNewChange(event.target.value)}
          />
        </label>
        <label>
          Nhập lại mật khẩu mới
          <input
            type="password"
            value={props.passwordConfirm}
            onChange={(event) => props.onPasswordConfirmChange(event.target.value)}
          />
        </label>
      </div>
      {props.passwordError ? <div className="alert">{props.passwordError}</div> : null}
      <div className="button-row">
        <button className="primary-button" disabled={props.busy} onClick={props.onChangePassword} type="button">
          Đổi mật khẩu
        </button>
        <button className="secondary-button" disabled={props.busy} onClick={props.onLogout} type="button">
          Đăng xuất
        </button>
      </div>
      <div className="user-preference-row">
        <div>
          <strong>Trợ lý EcoPet</strong>
          <span>Hiển thị chatbot nổi và gợi ý nhỏ trên dashboard.</span>
        </div>
        <label className="toggle-switch">
          <input
            aria-label="Trợ lý EcoPet"
            checked={props.chatbotEnabled}
            onChange={(event) => props.onChatbotEnabledChange(event.target.checked)}
            type="checkbox"
          />
          <span>{props.chatbotEnabled ? "Bật" : "Tắt"}</span>
        </label>
      </div>
    </section>
  );
}
