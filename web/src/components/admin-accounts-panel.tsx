"use client";

import { KeyRound, RotateCcw, ShieldCheck, UserPlus, UsersRound } from "lucide-react";

import type { AccountDTO, AuthRole, KnowledgeCatalogResponse, KnowledgeEntry, KnowledgeEvaluateResponse } from "@/lib/agent";
import { AdminAiTrainingPanel } from "@/components/admin-ai-training-panel";
import { ChatPanel } from "@/components/chat/chat-panel";
import type { AiChatResponse } from "@/lib/agent";

type AdminAccountsPanelProps = {
  accounts: AccountDTO[];
  busy: boolean;
  chatAnswer: AiChatResponse | null;
  chatQuestion: string;
  createPassword: string;
  createRole: AuthRole;
  createUsername: string;
  knowledgeCatalog: KnowledgeCatalogResponse | null;
  knowledgeEvaluation: KnowledgeEvaluateResponse | null;
  resetPassword: string;
  selectedOwner: string;
  onAskChat: (value?: string) => void;
  onBackfillOwner: () => void;
  onChatQuestionChange: (value: string) => void;
  onCreateAccount: () => void;
  onCreatePasswordChange: (value: string) => void;
  onCreateRoleChange: (value: AuthRole) => void;
  onCreateUsernameChange: (value: string) => void;
  onEvaluateKnowledge: (question: string, role: AuthRole) => void;
  onPatchKnowledge: (entry: KnowledgeEntry, patch: Partial<Pick<KnowledgeEntry, "enabled">>) => void;
  onRefresh: () => void;
  onReloadKnowledge: () => void;
  onResetPassword: (username: string) => void;
  onResetPasswordChange: (value: string) => void;
  onSelectedOwnerChange: (value: string) => void;
  onToggleActive: (username: string, active: boolean) => void;
  onUpsertKnowledge: (payload: {
    id?: string;
    title: string;
    roles: AuthRole[];
    keywords: string[];
    text: string;
    enabled: boolean;
  }) => void;
};

export function AdminAccountsPanel({
  accounts,
  busy,
  chatAnswer,
  chatQuestion,
  createPassword,
  createRole,
  createUsername,
  knowledgeCatalog,
  knowledgeEvaluation,
  resetPassword,
  selectedOwner,
  onAskChat,
  onBackfillOwner,
  onChatQuestionChange,
  onCreateAccount,
  onCreatePasswordChange,
  onCreateRoleChange,
  onCreateUsernameChange,
  onEvaluateKnowledge,
  onPatchKnowledge,
  onRefresh,
  onReloadKnowledge,
  onResetPassword,
  onResetPasswordChange,
  onSelectedOwnerChange,
  onToggleActive,
  onUpsertKnowledge
}: AdminAccountsPanelProps) {
  return (
    <section className="content-grid accounts-grid">
      <div className="panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Tài khoản</span>
            <h2>Quản lý tài khoản local</h2>
          </div>
          <button
            aria-label="Làm mới danh sách tài khoản"
            className="icon-button"
            disabled={busy}
            onClick={onRefresh}
            title="Làm mới"
            type="button"
          >
            <RotateCcw size={17} />
            <span>Làm mới</span>
          </button>
        </div>

        <div className="account-table">
          {accounts.map((account) => (
            <article className="account-row-card" key={account.id}>
              <div className="account-row-main">
                <div className="account-avatar">
                  {account.role === "admin" ? <ShieldCheck size={18} /> : <UsersRound size={18} />}
                </div>
                <div>
                  <strong>{account.username}</strong>
                  <span>
                    {account.role} - {account.is_active ? "đang hoạt động" : "đã vô hiệu"}
                    {account.password_default ? " - bắt buộc đổi mật khẩu" : ""}
                  </span>
                </div>
              </div>
              <div className="button-row">
                <button
                  className={account.is_active ? "danger-button compact-button" : "secondary-button compact-button"}
                  disabled={busy}
                  onClick={() => onToggleActive(account.username, !account.is_active)}
                  type="button"
                >
                  <span>{account.is_active ? "Vô hiệu" : "Kích hoạt"}</span>
                </button>
                <button
                  className="secondary-button compact-button"
                  disabled={busy || resetPassword.length < 8}
                  onClick={() => onResetPassword(account.username)}
                  type="button"
                >
                  <KeyRound size={15} />
                  <span>Đặt lại</span>
                </button>
              </div>
            </article>
          ))}
        </div>
      </div>

      <aside className="side-panel account-actions-panel">
        <div>
          <span className="eyebrow">Tạo mới</span>
          <h2>Thêm tài khoản</h2>
        </div>
        <div className="form-grid one-col">
          <label>
            Tên đăng nhập
            <input onChange={(event) => onCreateUsernameChange(event.target.value)} value={createUsername} />
          </label>
          <label>
            Vai trò
            <select onChange={(event) => onCreateRoleChange(event.target.value as AuthRole)} value={createRole}>
              <option value="user">user</option>
              <option value="admin">admin</option>
            </select>
          </label>
          <label>
            Mật khẩu tạm thời
            <input
              minLength={8}
              onChange={(event) => onCreatePasswordChange(event.target.value)}
              type="password"
              value={createPassword}
            />
          </label>
          <button
            className="primary-button"
            disabled={busy || !createUsername.trim() || createPassword.length < 8}
            onClick={onCreateAccount}
            type="button"
          >
            <UserPlus size={17} />
            <span>Tạo tài khoản</span>
          </button>
        </div>

        <div className="divider" />
        <label>
          Mật khẩu đặt lại
          <input
            minLength={8}
            onChange={(event) => onResetPasswordChange(event.target.value)}
            type="password"
            value={resetPassword}
          />
        </label>

        <div className="divider" />
        <label>
          Gán chủ sở hữu cho lịch sử cũ
          <select onChange={(event) => onSelectedOwnerChange(event.target.value)} value={selectedOwner}>
            <option value="">Chọn chủ sở hữu</option>
            {accounts
              .filter((account) => account.role === "user")
              .map((account) => (
                <option key={account.id} value={account.username}>
                  {account.username}
                </option>
              ))}
          </select>
        </label>
        <button className="secondary-button" disabled={busy || !selectedOwner} onClick={onBackfillOwner} type="button">
          <span>Gán chủ sở hữu</span>
        </button>
      </aside>

      <ChatPanel
        answer={chatAnswer}
        busy={busy}
        label="Chatbot Admin"
        placeholder="Hỏi về trạng thái thiết bị, dữ liệu 30 ngày, confidence hoặc vận hành."
        question={chatQuestion}
        statusText="DeepSeek dùng ngữ cảnh tổng hợp của hệ thống, không gửi ảnh/path/token."
        title="Trợ lý vận hành"
        persona="admin"
        onAsk={onAskChat}
        onQuestionChange={onChatQuestionChange}
      />

      <AdminAiTrainingPanel
        busy={busy}
        catalog={knowledgeCatalog}
        evaluation={knowledgeEvaluation}
        onEvaluate={onEvaluateKnowledge}
        onPatch={onPatchKnowledge}
        onReload={onReloadKnowledge}
        onUpsert={onUpsertKnowledge}
      />
    </section>
  );
}
