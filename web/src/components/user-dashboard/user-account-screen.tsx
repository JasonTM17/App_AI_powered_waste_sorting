"use client";

import { Bell, KeyRound, LogOut, MessageCircle, ShieldCheck, UserRound } from "lucide-react";

import type { UserDashboardPanelProps } from "./user-dashboard-types";

export function UserAccountScreen(props: UserDashboardPanelProps) {
  const quotaSource = props.chatAnswer ?? props.advisor;
  const quotaLimit = quotaSource?.quota_limit ?? 36;
  const quotaRemaining = quotaSource?.quota_remaining ?? null;
  const quotaUsed = quotaSource?.quota_used ?? null;
  const quotaLabel =
    quotaRemaining === null || quotaUsed === null
      ? "36 lượt hỏi mỗi tháng"
      : `${quotaRemaining}/${quotaLimit} lượt còn lại trong tháng`;
  const owner = props.device?.owner_username || props.auth?.username || "Người dùng";
  return (
    <section className="user-account-screen">
      <div className="user-account-header">
        <div>
          <span className="eyebrow">Cài đặt tài khoản</span>
          <h2>{props.auth?.username || "User"}</h2>
          <p>Quản lý đăng nhập, bảo mật và tùy chọn EcoPet của bạn.</p>
        </div>
        <div className="account-avatar" aria-hidden="true">
          <UserRound size={26} />
        </div>
      </div>

      <div className="user-account-grid">
        <section className="user-panel account-card identity-card">
          <div className="user-panel-heading inline">
            <div>
              <span className="eyebrow">Thông tin cá nhân</span>
              <strong>Hồ sơ local</strong>
            </div>
            <ShieldCheck size={21} />
          </div>
          <div className="account-readonly-list">
            <div>
              <span>Tên đăng nhập</span>
              <strong>{props.auth?.username || "User"}</strong>
            </div>
            <div>
              <span>Quyền truy cập</span>
              <strong>Người dùng</strong>
            </div>
            <div>
              <span>Chủ thiết bị</span>
              <strong>{owner}</strong>
            </div>
            <div>
              <span>Phiên đăng nhập</span>
              <strong>{props.auth?.session_expires_at ? "Đang hoạt động" : "Local"}</strong>
            </div>
          </div>
        </section>

        <section className="user-panel account-card security-card">
          <div className="user-panel-heading inline">
            <div>
              <span className="eyebrow">Bảo mật tài khoản</span>
              <strong>Đổi mật khẩu</strong>
            </div>
            <KeyRound size={21} />
          </div>
          <div className="account-form-grid">
            <label>
              Mật khẩu hiện tại
              <input
                autoComplete="current-password"
                type="password"
                value={props.passwordCurrent}
                onChange={(event) => props.onPasswordCurrentChange(event.target.value)}
              />
            </label>
            <label>
              Mật khẩu mới
              <input
                autoComplete="new-password"
                type="password"
                value={props.passwordNew}
                onChange={(event) => props.onPasswordNewChange(event.target.value)}
              />
            </label>
            <label>
              Nhập lại mật khẩu mới
              <input
                autoComplete="new-password"
                type="password"
                value={props.passwordConfirm}
                onChange={(event) => props.onPasswordConfirmChange(event.target.value)}
              />
            </label>
          </div>
          {props.passwordError ? <div className="alert">{props.passwordError}</div> : null}
          <div className="button-row">
            <button className="primary-button" disabled={props.busy} onClick={props.onChangePassword} type="button">
              <KeyRound size={17} />
              <span>Đổi mật khẩu</span>
            </button>
            <button className="secondary-button" disabled={props.busy} onClick={props.onLogout} type="button">
              <LogOut size={17} />
              <span>Đăng xuất</span>
            </button>
          </div>
        </section>

        <section className="user-panel account-card preference-card">
          <div className="user-panel-heading inline">
            <div>
              <span className="eyebrow">Tùy chọn thông báo</span>
              <strong>EcoPet và nhắc nhở</strong>
            </div>
            <Bell size={21} />
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
          <div className="account-readonly-list compact">
            <div>
              <span>Nhắc lịch phân loại</span>
              <strong>Theo dữ liệu local</strong>
            </div>
            <div>
              <span>Cảnh báo thói quen</span>
              <strong>Hiển thị trong EcoPet</strong>
            </div>
          </div>
        </section>

        <section className="user-panel account-card ai-usage-card">
          <div className="user-panel-heading inline">
            <div>
              <span className="eyebrow">Lượt hỏi EcoPet</span>
              <strong>{quotaLabel}</strong>
            </div>
            <MessageCircle size={21} />
          </div>
          <div className="quota-meter" aria-label="Lượt hỏi EcoPet trong tháng">
            <span style={{ width: `${quotaUsed === null ? 0 : Math.min(100, (quotaUsed / quotaLimit) * 100)}%` }} />
          </div>
          <p className="account-note">
            Lượt hỏi áp dụng cho chat EcoPet và phần tư vấn. Đầu tháng hệ thống tự mở lại 36 lượt mới.
          </p>
        </section>
      </div>
    </section>
  );
}
