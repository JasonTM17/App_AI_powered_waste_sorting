"use client";

import { ImageIcon, ListChecks } from "lucide-react";

import type { UserHistoryItem } from "@/lib/agent";
import { openAgentBlob, userHistoryImagePath } from "@/lib/agent";

const categoryLabels: Record<UserHistoryItem["category"], string> = {
  organic: "Hữu cơ",
  inorganic: "Vô cơ",
  recyclable: "Tái chế"
};

type UserHistoryPanelProps = {
  imageToken: string;
  rows: UserHistoryItem[];
};

export function UserHistoryPanel({ imageToken, rows }: UserHistoryPanelProps) {
  return (
    <section className="user-panel user-history-panel">
      <div className="user-panel-heading inline">
        <div>
          <span className="eyebrow">Lịch sử của bạn</span>
          <strong>Phân loại gần đây</strong>
        </div>
        <ListChecks size={21} />
      </div>
      <div className="user-history-list">
        {rows.length ? (
          rows.map((row) => (
            <article className="user-history-row" key={row.id}>
              <div>
                <strong>{row.cls_name || "Chưa rõ"}</strong>
                <span>
                  {formatDate(row.ts)} · {categoryLabels[row.category]} · {Math.round(row.confidence * 100)}%
                </span>
              </div>
              <small>{row.route_label || `Thùng ${row.bin_index ?? "-"}`}</small>
              {row.image_available ? (
                <button
                  className="history-image-link"
                  onClick={() => void openAgentBlob(userHistoryImagePath(row.id, "annotated"), imageToken)}
                  type="button"
                >
                  <ImageIcon size={16} />
                  <span>Ảnh</span>
                </button>
              ) : null}
            </article>
          ))
        ) : (
          <div className="empty-state">Chưa có lịch sử thuộc tài khoản này.</div>
        )}
      </div>
    </section>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value || "-";
  }
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit"
  }).format(date);
}
