"use client";

import { type CSSProperties, type PointerEvent, useEffect, useRef, useState } from "react";

import { ChatbotPet, ChatPanel, type ChatTranscriptMessage } from "@/components/chat/chat-panel";
import type { AiChatResponse } from "@/lib/agent";

type RoleChatbotLauncherProps = {
  answer: AiChatResponse | null;
  busy: boolean;
  label: string;
  placeholder: string;
  question: string;
  role: "admin" | "user";
  statusText: string;
  title: string;
  defaultOpen?: boolean;
  onAsk: (value?: string) => void;
  onQuestionChange: (value: string) => void;
};

type DragState = {
  height: number;
  moved: boolean;
  originX: number;
  originY: number;
  pointerId: number;
  startX: number;
  startY: number;
  width: number;
};

type FloatingPosition = {
  x: number;
  y: number;
};

const DRAG_THRESHOLD_PX = 6;
const STORAGE_PREFIX = "trash-sorter-chatbot-pet-position";
const ADMIN_PROMPT_CLOUDS = [
  "Camera USB đang ổn không?",
  "Tóm tắt vận hành hôm nay",
  "Vì sao AI confidence thấp?"
];
const USER_PROMPT_CLOUDS = [
  "Hôm nay bạn thế nào?",
  "Hôm nay mình bỏ rác gì?",
  "Mình có uống nhiều nước ngọt không?"
];

export function RoleChatbotLauncher({
  answer,
  busy,
  defaultOpen = false,
  label,
  placeholder,
  question,
  role,
  statusText,
  title,
  onAsk,
  onQuestionChange
}: RoleChatbotLauncherProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [dragging, setDragging] = useState(false);
  const [compact, setCompact] = useState(false);
  const [position, setPosition] = useState<FloatingPosition | null>(null);
  const [promptIndex, setPromptIndex] = useState(0);
  const [showPromptCloud, setShowPromptCloud] = useState(false);
  const [transcript, setTranscript] = useState<ChatTranscriptMessage[]>([]);
  const dragRef = useRef<DragState | null>(null);
  const lastAnswerRef = useRef<AiChatResponse | null>(null);
  const previousBusyRef = useRef(false);
  const pendingAssistantIdRef = useRef<string | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const cloudHideTimerRef = useRef<number | undefined>(undefined);
  const suppressClickRef = useRef(false);
  const storageKey = `${STORAGE_PREFIX}-${role}`;
  const promptClouds = role === "admin" ? ADMIN_PROMPT_CLOUDS : USER_PROMPT_CLOUDS;
  const promptCloud = promptClouds[promptIndex % promptClouds.length];

  useEffect(() => {
    if (defaultOpen) {
      setOpen(true);
    }
  }, [defaultOpen]);

  useEffect(() => {
    return () => {
      if (cloudHideTimerRef.current) {
        window.clearTimeout(cloudHideTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!answer || answer === lastAnswerRef.current || !pendingAssistantIdRef.current) {
      return;
    }
    lastAnswerRef.current = answer;
    const pendingId = pendingAssistantIdRef.current;
    pendingAssistantIdRef.current = null;
    setTranscript((current) =>
      current.map((message) =>
        message.id === pendingId
          ? {
              id: pendingId,
              role: "assistant",
              text: answer.message || defaultAssistantMessage(role)
            }
          : message
      )
    );
  }, [answer]);

  useEffect(() => {
    if (previousBusyRef.current && !busy && pendingAssistantIdRef.current) {
      const pendingId = pendingAssistantIdRef.current;
      pendingAssistantIdRef.current = null;
      setTranscript((current) =>
        current.map((message) =>
          message.id === pendingId
            ? {
                id: pendingId,
                role: "assistant",
                text: fallbackAssistantMessage(role)
              }
            : message
        )
      );
    }
    previousBusyRef.current = busy;
  }, [busy]);

  useEffect(() => {
    const applyViewportState = () => {
      setCompact(window.innerWidth <= 760);
      setPosition((current) => (current ? clampFloatingPosition(current.x, current.y) : current));
    };
    applyViewportState();

    try {
      const saved = window.localStorage.getItem(storageKey);
      if (saved) {
        const parsed = JSON.parse(saved) as Partial<FloatingPosition>;
        if (typeof parsed.x === "number" && typeof parsed.y === "number") {
          setPosition(clampFloatingPosition(parsed.x, parsed.y));
        }
      }
    } catch {
      window.localStorage.removeItem(storageKey);
    }

    window.addEventListener("resize", applyViewportState);
    return () => window.removeEventListener("resize", applyViewportState);
  }, [storageKey]);

  useEffect(() => {
    if (open) {
      setShowPromptCloud(false);
      return;
    }
    const rotatePrompt = () => {
      setPromptIndex((current) => current + 1);
    };
    const interval = window.setInterval(rotatePrompt, 9000);
    return () => {
      window.clearInterval(interval);
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    const handlePointerDown = (event: globalThis.PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("pointerdown", handlePointerDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [open]);

  const triggerStyle: CSSProperties | undefined = position
    ? {
        bottom: "auto",
        left: position.x,
        right: "auto",
        top: position.y
      }
    : undefined;
  const panelStyle = open && position && !compact ? panelPositionNearTrigger(position) : undefined;
  const cloudStyle = position ? promptCloudPositionNearTrigger(position, compact) : undefined;

  const openChat = () => {
    if (suppressClickRef.current) {
      return;
    }
    setOpen(true);
  };
  const openWithPrompt = (value: string) => {
    onQuestionChange(value);
    setShowPromptCloud(false);
    setOpen(true);
  };
  const showCloud = () => {
    if (cloudHideTimerRef.current) {
      window.clearTimeout(cloudHideTimerRef.current);
    }
    if (!dragging) {
      setShowPromptCloud(true);
    }
  };
  const scheduleHideCloud = () => {
    if (cloudHideTimerRef.current) {
      window.clearTimeout(cloudHideTimerRef.current);
    }
    cloudHideTimerRef.current = window.setTimeout(() => setShowPromptCloud(false), 170);
  };

  const askChat = (value?: string) => {
    const text = (value ?? question).trim() || defaultQuestion(role);
    const stamp = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const pendingAssistantId = `assistant-${stamp}`;
    pendingAssistantIdRef.current = pendingAssistantId;
    setTranscript((current) => [
      ...current.filter((message) => !message.pending),
      { id: `user-${stamp}`, role: "user", text },
      { id: pendingAssistantId, pending: true, role: "assistant", text: "Đang tạo câu trả lời..." }
    ]);
    onQuestionChange("");
    onAsk(text);
  };

  const handlePointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    dragRef.current = {
      height: rect.height,
      moved: false,
      originX: rect.left,
      originY: rect.top,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      width: rect.width
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: PointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) {
      return;
    }
    const deltaX = event.clientX - drag.startX;
    const deltaY = event.clientY - drag.startY;
    if (Math.abs(deltaX) + Math.abs(deltaY) > DRAG_THRESHOLD_PX) {
      drag.moved = true;
      setDragging(true);
      setShowPromptCloud(false);
    }
    if (!drag.moved) {
      return;
    }
    setPosition(clampFloatingPosition(drag.originX + deltaX, drag.originY + deltaY, drag.width, drag.height));
  };

  const handlePointerUp = (event: PointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) {
      return;
    }
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (drag.moved) {
      const nextPosition = clampFloatingPosition(
        drag.originX + event.clientX - drag.startX,
        drag.originY + event.clientY - drag.startY,
        drag.width,
        drag.height
      );
      setPosition(nextPosition);
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(nextPosition));
      } catch {
        // Keep dragging usable even when storage is disabled.
      }
      suppressClickRef.current = true;
      window.setTimeout(() => {
        suppressClickRef.current = false;
      }, 0);
    }
    setDragging(false);
    dragRef.current = null;
  };

  return (
    <div className={`chatbot-launcher chatbot-launcher-${role} ${open ? "open" : ""}`} ref={rootRef}>
      {open ? (
        <ChatPanel
          answer={answer}
          busy={busy}
          label={label}
          placeholder={placeholder}
          question={question}
          showPet={false}
          statusText={statusText}
          style={panelStyle}
          title={title}
          transcript={transcript}
          persona={role === "user" ? "ecopet" : "admin"}
          variant="dock"
          onAsk={askChat}
          onClose={() => setOpen(false)}
          onQuestionChange={onQuestionChange}
        />
      ) : (
        <>
          {showPromptCloud && !dragging ? (
            <button
              aria-label={`Mở trợ lý với câu hỏi: ${promptCloud}`}
              className="chatbot-prompt-cloud is-visible"
              onClick={() => openWithPrompt(promptCloud)}
              onBlur={scheduleHideCloud}
              onFocus={showCloud}
              onPointerEnter={showCloud}
              onPointerLeave={scheduleHideCloud}
              style={cloudStyle}
              type="button"
            >
              {promptCloud}
            </button>
          ) : null}
          <button
            aria-label="Mở trợ lý AI"
            className={`chatbot-pet-trigger ${dragging ? "dragging" : ""} ${position ? "is-dragged" : ""}`}
            onClick={openChat}
            onBlur={scheduleHideCloud}
            onFocus={showCloud}
            onPointerCancel={handlePointerUp}
            onPointerDown={handlePointerDown}
            onPointerEnter={showCloud}
            onPointerLeave={scheduleHideCloud}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            style={triggerStyle}
            title={`${title} - kéo để di chuyển, bấm để mở`}
            type="button"
          >
            <ChatbotPet />
          </button>
        </>
      )}
    </div>
  );
}

function promptCloudPositionNearTrigger(position: FloatingPosition, compact: boolean): CSSProperties {
  const width = compact ? 188 : 230;
  const height = compact ? 46 : 48;
  const triggerSize = compact ? 56 : 58;
  const left = position.x + triggerSize / 2 - width / 2;
  const top = position.y - height - 6;
  return {
    bottom: "auto",
    left: Math.min(Math.max(12, left), window.innerWidth - width - 12),
    right: "auto",
    top: Math.min(Math.max(12, top), window.innerHeight - height - 12)
  };
}

function clampFloatingPosition(x: number, y: number, width = 58, height = 58): FloatingPosition {
  const margin = 12;
  const maxX = Math.max(margin, window.innerWidth - width - margin);
  const maxY = Math.max(margin, window.innerHeight - height - margin);
  return {
    x: Math.min(Math.max(margin, x), maxX),
    y: Math.min(Math.max(margin, y), maxY)
  };
}

function defaultQuestion(role: "admin" | "user") {
  return role === "admin" ? "Tóm tắt hệ thống hôm nay." : "Hôm nay bạn thế nào?";
}

function defaultAssistantMessage(role: "admin" | "user") {
  return role === "admin"
    ? "Chào bạn, mình sẵn sàng hỗ trợ vận hành EcoSort. Bạn muốn kiểm tra phần nào?"
    : "Chào bạn, hôm nay mình cùng xem thói quen phân loại rác nhé.";
}

function fallbackAssistantMessage(role: "admin" | "user") {
  return role === "admin"
    ? "Chưa nhận được phản hồi từ trợ lý. Bạn kiểm tra kết nối agent hoặc cấu hình DeepSeek rồi thử lại."
    : "EcoPet chưa phản hồi kịp. Bạn thử hỏi lại sau một chút nhé; biểu đồ và lịch sử vẫn dùng bình thường.";
}

function panelPositionNearTrigger(position: FloatingPosition): CSSProperties {
  const margin = 16;
  const panelWidth = Math.min(420, window.innerWidth - margin * 2);
  const panelHeight = Math.min(510, window.innerHeight - margin * 2);
  const triggerSize = 58;
  const placeRight = position.x + triggerSize + margin + panelWidth <= window.innerWidth;
  const left = placeRight ? position.x + triggerSize + margin : position.x - panelWidth - margin;
  return {
    bottom: "auto",
    left: Math.min(Math.max(margin, left), window.innerWidth - panelWidth - margin),
    right: "auto",
    top: Math.min(Math.max(margin, position.y - panelHeight + triggerSize), window.innerHeight - panelHeight - margin)
  };
}
