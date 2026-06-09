"use client";

import { Bot, Send, Sparkles, X } from "lucide-react";
import { useEffect, useRef, type CSSProperties } from "react";

import type { AiChatResponse } from "@/lib/agent";

export type ChatTranscriptMessage = {
  id: string;
  pending?: boolean;
  role: "assistant" | "user";
  text: string;
};

type ChatPanelProps = {
  answer: AiChatResponse | null;
  busy: boolean;
  label: string;
  placeholder: string;
  question: string;
  statusText: string;
  style?: CSSProperties;
  title: string;
  transcript?: ChatTranscriptMessage[];
  persona?: "admin" | "ecopet";
  variant?: "inline" | "dock";
  showPet?: boolean;
  onClose?: () => void;
  onAsk: (value?: string) => void;
  onQuestionChange: (value: string) => void;
};

export function ChatPanel({
  answer,
  busy,
  label,
  placeholder,
  question,
  statusText,
  style,
  title,
  transcript = [],
  persona = "ecopet",
  variant = "inline",
  showPet = true,
  onClose,
  onAsk,
  onQuestionChange
}: ChatPanelProps) {
  const prompts = answer?.quick_prompts ?? [];
  const isDock = variant === "dock";
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const statusClass = answer?.available ? "advisor-status online" : "advisor-status offline";
  const answerText =
    answer?.message || initialMessage(persona);
  const dockPrompts = prompts.length ? prompts.slice(0, 3) : defaultPrompts(persona);
  useEffect(() => {
    if (!isDock) {
      return;
    }
    const body = bodyRef.current;
    if (body) {
      body.scrollTop = body.scrollHeight;
    }
  }, [answer?.message, busy, isDock, transcript.length]);

  if (isDock) {
    const headerTitle = persona === "ecopet" ? "EcoPet" : title;
    const online = answer?.available || !answer;
    const dockMessages: ChatTranscriptMessage[] = transcript.length
      ? transcript
      : [{ id: "initial-assistant", pending: busy, role: "assistant", text: answerText }];
    return (
      <section
        aria-label={title}
        className={`chat-panel chat-panel-dock stitch-chat-panel ${persona === "admin" ? "admin-chat" : "ecopet-chat"}`}
        role="dialog"
        style={style}
      >
        <div className="stitch-chat-header">
          <div className="stitch-chat-identity">
            <ChatbotAvatar />
            <div>
              <strong>{headerTitle}</strong>
              <small>{chatSubtitle(persona)}</small>
              <span className={online ? "stitch-online" : "stitch-offline"}>
                <i />
                {online ? "Online" : "Cần cấu hình"}
              </span>
            </div>
          </div>
          {onClose ? (
            <button className="stitch-chat-close" onClick={onClose} type="button" aria-label="Đóng trợ lý AI">
              <X size={18} />
            </button>
          ) : null}
        </div>

        <div className="stitch-chat-body" aria-live="polite" ref={bodyRef}>
          <div className="stitch-chat-context-row" aria-label="Trạng thái trợ lý AI">
            <span>{answer?.available ? "Bộ nhớ dự án đang bật" : "Chế độ local an toàn"}</span>
            <span>{answer?.model || "deepseek-v4-flash"}</span>
          </div>
          {dockMessages.map((message) => (
            <div className={`stitch-chat-message-row ${message.role}`} key={message.id}>
              {message.role === "assistant" ? <ChatbotAvatar compact /> : null}
              <div className={`stitch-chat-bubble ${message.role} ${message.pending ? "pending" : ""}`}>
                {message.pending ? (
                  <div className="chat-loading-state" aria-label="Đang tạo câu trả lời">
                    <span />
                    <span />
                    <span />
                  </div>
                ) : (
                  <FormattedChatText text={message.text} />
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="stitch-chat-prompts">
          <span className="stitch-chat-prompts-label">Gợi ý nhanh</span>
          {dockPrompts.map((prompt) => (
            <button disabled={busy} key={prompt} onClick={() => onAsk(prompt)} type="button">
              {prompt}
            </button>
          ))}
        </div>

        <div className="stitch-chat-input-row">
          <textarea
            className="stitch-chat-input"
            maxLength={800}
            onChange={(event) => onQuestionChange(event.target.value)}
            placeholder={placeholder}
            value={question}
          />
          <button
            aria-busy={busy}
            aria-label={busy ? "Đang hỏi AI" : "Gửi câu hỏi cho AI"}
            disabled={busy}
            onClick={() => onAsk()}
            type="button"
          >
            <Send size={18} />
          </button>
        </div>
      </section>
    );
  }
  return (
    <section
      aria-label={isDock ? title : undefined}
      className={`user-panel chat-panel ${isDock ? "chat-panel-dock" : ""}`}
      role={isDock ? "dialog" : undefined}
      style={style}
    >
      {isDock && showPet ? <ChatbotPet /> : null}
      {isDock ? <div className="chat-drawer-handle" aria-hidden="true" /> : null}
      {onClose ? (
        <button className="chat-panel-close" onClick={onClose} type="button" aria-label="Đóng trợ lý AI">
          <X size={16} />
        </button>
      ) : null}
      <div className="user-panel-heading inline">
        <div>
          <span className="eyebrow">{label}</span>
          <strong>{title}</strong>
        </div>
        <Bot size={21} />
      </div>
      <div className={statusClass}>
        <Sparkles size={16} />
        <span>{answer ? `${answer.provider} ${answer.model || ""}`.trim() : statusText}</span>
      </div>
      {answer?.profile ? (
        <div className="chat-meta-row">
          <span>{answer.profile}</span>
          {answer.knowledge_used?.slice(0, 2).map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      ) : null}
      {prompts.length ? (
        <div className="quick-prompt-row">
          {prompts.slice(0, 4).map((prompt) => (
            <button disabled={busy} key={prompt} onClick={() => onAsk(prompt)} type="button">
              {prompt}
            </button>
          ))}
        </div>
      ) : null}
      <textarea
        className="advisor-question"
        maxLength={800}
        onChange={(event) => onQuestionChange(event.target.value)}
        placeholder={placeholder}
        value={question}
      />
      <button
        className="primary-button advisor-button"
        disabled={busy}
        onClick={() => onAsk()}
        type="button"
        aria-busy={busy}
      >
        <Send size={17} />
        <span>{busy ? "Đang hỏi..." : "Hỏi AI"}</span>
      </button>
      <div className="advisor-answer chat-answer" aria-live="polite">
        {busy ? (
          <div className="chat-loading-state" aria-label="Đang tạo câu trả lời">
            <span />
            <span />
            <span />
          </div>
        ) : (
          <FormattedChatText text={answerText} />
        )}
      </div>
    </section>
  );
}

function FormattedChatText({ text }: { text: string }) {
  const lines = cleanChatMarkdown(text)
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) {
    return null;
  }
  return (
    <>
      {lines.map((line, index) => (
        <span className="chat-text-line" key={`${line}-${index}`}>
          {line.replace(/^\s*[-*]\s+/, "• ").replace(/^#{1,6}\s+/, "")}
        </span>
      ))}
    </>
  );
}

function cleanChatMarkdown(value: string) {
  return value
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__(.*?)__/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\r\n/g, "\n")
    .trim();
}

function defaultPrompts(persona: "admin" | "ecopet") {
  if (persona === "admin") {
    return ["Tình trạng máy hôm nay", "Camera có ổn không?", "Có cảnh báo nào không?"];
  }
  return ["Hôm nay bạn thế nào?", "Hôm nay mình bỏ rác gì?", "Mình có uống nhiều nước ngọt không?"];
}

function initialMessage(persona: "admin" | "ecopet") {
  if (persona === "admin") {
    return "Chào bạn, mình sẵn sàng hỗ trợ vận hành EcoSort. Bạn muốn kiểm tra phần nào?";
  }
  return "Chào bạn, hôm nay mình cùng xem thói quen phân loại rác nhé.";
}

function chatSubtitle(persona: "admin" | "ecopet") {
  return persona === "admin" ? "Theo dõi vận hành máy" : "Bạn đồng hành phân loại rác";
}

function ChatbotAvatar({ compact = false }: { compact?: boolean }) {
  return (
    <span className={compact ? "chatbot-avatar compact" : "chatbot-avatar"} aria-hidden="true">
      <ChatbotPet />
    </span>
  );
}

export function ChatbotPet() {
  return (
    <div className="chatbot-pet" aria-hidden="true">
      <div className="chatbot-pet-hop">
        <svg viewBox="0 0 112 92" focusable="false">
          <defs>
            <linearGradient id="pet-face-gradient" x1="28" x2="86" y1="28" y2="66" gradientUnits="userSpaceOnUse">
              <stop stopColor="#EAF8E7" />
              <stop offset="1" stopColor="#D7ECFF" />
            </linearGradient>
          </defs>
          <ellipse className="pet-shadow" cx="56" cy="82" rx="32" ry="6" />
          <path className="pet-sprout-stem" d="M56 20c-1-7 2-11 7-14" />
          <path className="pet-sprout-leaf pet-sprout-left" d="M57 11c-9-7-18-4-20 5 8 4 16 3 20-5Z" />
          <path className="pet-sprout-leaf pet-sprout-right" d="M62 8c7-7 17-5 20 3-7 5-16 5-20-3Z" />
          <path className="pet-ear pet-ear-left" d="M25 43c-8 2-13 7-14 14 6 3 13 0 18-7Z" />
          <path className="pet-ear pet-ear-right" d="M87 43c8 2 13 7 14 14-6 3-13 0-18-7Z" />
          <rect className="pet-body" x="22" y="22" width="68" height="58" rx="24" />
          <rect className="pet-face" x="32" y="33" width="48" height="28" rx="14" />
          <circle className="pet-cheek pet-cheek-left" cx="38" cy="54" r="3.5" />
          <circle className="pet-cheek pet-cheek-right" cx="74" cy="54" r="3.5" />
          <path className="pet-eye pet-eye-left" d="M43 45c3-4 8-4 11 0" />
          <path className="pet-eye pet-eye-right" d="M58 45c3-4 8-4 11 0" />
          <path className="pet-smile" d="M48 54c5 5 11 5 16 0" />
          <path className="pet-panel" d="M42 68h28" />
          <path className="pet-arm pet-arm-left" d="M24 57c-6 1-10 5-12 10" />
          <path className="pet-arm pet-arm-right" d="M88 57c6 1 10 5 12 10" />
          <path className="pet-leg pet-leg-left" d="M43 79l-3 7" />
          <path className="pet-leg pet-leg-right" d="M69 79l3 7" />
          <circle className="pet-spark pet-spark-left" cx="24" cy="25" r="2" />
          <circle className="pet-spark pet-spark-right" cx="89" cy="27" r="2.5" />
        </svg>
      </div>
    </div>
  );
}
