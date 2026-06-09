"use client";

import { BrainCircuit, CheckCircle2, FlaskConical, Pencil, RotateCcw, Save, ToggleLeft, ToggleRight } from "lucide-react";
import { useMemo, useState } from "react";

import type { AuthRole, KnowledgeCatalogResponse, KnowledgeEntry, KnowledgeEvaluateResponse } from "@/lib/agent";

type KnowledgeDraft = {
  id?: string;
  title: string;
  roles: AuthRole[];
  keywords: string[];
  text: string;
  enabled: boolean;
};

type AdminAiTrainingPanelProps = {
  busy: boolean;
  catalog: KnowledgeCatalogResponse | null;
  evaluation: KnowledgeEvaluateResponse | null;
  onEvaluate: (question: string, role: AuthRole) => void;
  onPatch: (entry: KnowledgeEntry, patch: Partial<Pick<KnowledgeEntry, "enabled">>) => void;
  onReload: () => void;
  onUpsert: (payload: KnowledgeDraft) => void;
};

const emptyDraft: KnowledgeDraft = {
  title: "",
  roles: ["admin", "user"],
  keywords: [],
  text: "",
  enabled: true
};

export function AdminAiTrainingPanel({
  busy,
  catalog,
  evaluation,
  onEvaluate,
  onPatch,
  onReload,
  onUpsert
}: AdminAiTrainingPanelProps) {
  const [draft, setDraft] = useState<KnowledgeDraft>(emptyDraft);
  const [keywordText, setKeywordText] = useState("");
  const [evalQuestion, setEvalQuestion] = useState("Camera USB và UART đang lỗi thì kiểm tra gì trước?");
  const [evalRole, setEvalRole] = useState<AuthRole>("admin");
  const entries = catalog?.entries ?? [];
  const localEntries = useMemo(() => entries.filter((entry) => entry.source === "local").length, [entries]);
  const canSave = draft.title.trim().length > 0 && draft.text.trim().length > 0 && draft.roles.length > 0;

  const editEntry = (entry: KnowledgeEntry) => {
    setDraft({
      id: entry.id,
      title: entry.title,
      roles: entry.roles,
      keywords: entry.keywords,
      text: entry.text,
      enabled: entry.enabled
    });
    setKeywordText(entry.keywords.join(", "));
  };

  const saveDraft = () => {
    if (!canSave) {
      return;
    }
    onUpsert({
      ...draft,
      keywords: splitKeywords(keywordText)
    });
    setDraft(emptyDraft);
    setKeywordText("");
  };

  const toggleRole = (role: AuthRole) => {
    setDraft((current) => {
      const roles = current.roles.includes(role)
        ? current.roles.filter((item) => item !== role)
        : [...current.roles, role];
      return { ...current, roles };
    });
  };

  return (
    <section className="panel ai-training-panel">
      <div className="panel-toolbar">
        <div>
          <span className="eyebrow">Huấn luyện AI</span>
          <h2>Knowledge/RAG riêng cho EcoSort</h2>
        </div>
        <button className="icon-button" disabled={busy} onClick={onReload} title="Nạp lại knowledge" type="button">
          <RotateCcw size={17} />
          <span>Nạp lại</span>
        </button>
      </div>

      <div className="ai-training-summary">
        <span><CheckCircle2 size={15} /> {catalog?.enabled_total ?? 0}/{catalog?.total ?? 0} snippet bật</span>
        <span><BrainCircuit size={15} /> {localEntries} snippet local</span>
        <span>Model: deepseek-v4-flash</span>
      </div>
      {catalog?.error ? <div className="alert compact-alert">Knowledge local lỗi: {catalog.error}</div> : null}
      <p className="muted-copy">
        API key chỉ nằm ở backend `.env.local`. Panel này chỉ quản lý kiến thức domain; không hiển thị hoặc lưu key trong web.
      </p>

      <div className="ai-training-layout">
        <div className="ai-training-form">
          <label>
            Tiêu đề snippet
            <input
              value={draft.title}
              onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
              placeholder="Ví dụ: Quy trình xử lý camera mất tín hiệu"
            />
          </label>
          <label>
            Keywords
            <input
              value={keywordText}
              onChange={(event) => setKeywordText(event.target.value)}
              placeholder="camera, uart, confidence, mapping"
            />
          </label>
          <div className="segmented-control ai-role-toggle" aria-label="Role áp dụng">
            <button className={draft.roles.includes("admin") ? "active" : ""} onClick={() => toggleRole("admin")} type="button">
              Admin
            </button>
            <button className={draft.roles.includes("user") ? "active" : ""} onClick={() => toggleRole("user")} type="button">
              User
            </button>
          </div>
          <label>
            Nội dung huấn luyện
            <textarea
              rows={5}
              value={draft.text}
              onChange={(event) => setDraft((current) => ({ ...current, text: event.target.value }))}
              placeholder="Viết quy tắc, FAQ hoặc hướng dẫn vận hành ngắn gọn cho trợ lý."
            />
          </label>
          <button className="primary-button" disabled={busy || !canSave} onClick={saveDraft} type="button">
            <Save size={17} />
            <span>{draft.id ? "Lưu bản sửa" : "Thêm snippet"}</span>
          </button>
        </div>

        <div className="ai-training-list" aria-label="Danh sách knowledge snippets">
          {entries.map((entry) => (
            <article className={entry.enabled ? "knowledge-row" : "knowledge-row disabled"} key={entry.id}>
              <div>
                <strong>{entry.title}</strong>
                <span>{entry.roles.join(", ")} - {entry.source} - {entry.keywords.slice(0, 4).join(", ") || "không keyword"}</span>
              </div>
              <div className="button-row">
                <button className="secondary-button compact-button" disabled={busy} onClick={() => editEntry(entry)} type="button">
                  <Pencil size={14} />
                  <span>Sửa</span>
                </button>
                <button
                  className="secondary-button compact-button"
                  disabled={busy}
                  onClick={() => onPatch(entry, { enabled: !entry.enabled })}
                  type="button"
                >
                  {entry.enabled ? <ToggleRight size={15} /> : <ToggleLeft size={15} />}
                  <span>{entry.enabled ? "Tắt" : "Bật"}</span>
                </button>
              </div>
            </article>
          ))}
        </div>
      </div>

      <div className="ai-eval-panel">
        <div>
          <span className="eyebrow">Kiểm thử retrieval</span>
          <strong>Câu hỏi mẫu trước khi gọi DeepSeek</strong>
        </div>
        <div className="ai-eval-row">
          <select value={evalRole} onChange={(event) => setEvalRole(event.target.value as AuthRole)}>
            <option value="admin">Admin</option>
            <option value="user">User</option>
          </select>
          <input value={evalQuestion} onChange={(event) => setEvalQuestion(event.target.value)} />
          <button className="secondary-button" disabled={busy || !evalQuestion.trim()} onClick={() => onEvaluate(evalQuestion, evalRole)} type="button">
            <FlaskConical size={16} />
            <span>Test</span>
          </button>
        </div>
        {evaluation ? (
          <div className="ai-eval-result">
            <span>{evaluation.snippets.length} snippet, {evaluation.payload_chars} ký tự payload</span>
            <strong>{evaluation.snippets.map((item) => item.title).join(" · ")}</strong>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function splitKeywords(value: string) {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 30);
}
