"use client";

import { Camera, Check, CircleHelp } from "lucide-react";
import { useMemo, useState } from "react";

import type { HistoryRow } from "@/lib/agent";
import { historyImagePath, openAgentBlob } from "@/lib/agent";

type ReviewStatus = "human_verified" | "needs_review" | "no_evidence";

type HistoryPanelProps = {
  imageToken: string;
  rows: HistoryRow[];
  labelOptions?: string[];
  onOpenImage?: (row: HistoryRow) => Promise<void> | void;
  onReviewLabel?: (row: HistoryRow, label: string, status: ReviewStatus) => Promise<void>;
};

const STATUS_LABELS: Record<string, string> = {
  model_inferred: "AI suy ra",
  metadata_verified: "Metadata xác minh",
  human_verified: "Admin đã duyệt",
  needs_review: "Cần duyệt",
  no_evidence: "Không đủ bằng chứng"
};

export function HistoryPanel({
  imageToken,
  rows,
  labelOptions = [],
  onOpenImage,
  onReviewLabel
}: HistoryPanelProps) {
  const [statusFilter, setStatusFilter] = useState("all");
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [reviewingId, setReviewingId] = useState<number | null>(null);
  const visibleRows = useMemo(
    () => rows.filter((row) => statusFilter === "all" || row.label_status === statusFilter),
    [rows, statusFilter]
  );
  const options = useMemo(
    () => [...new Set(labelOptions.map((label) => label.trim()).filter(Boolean))].sort(),
    [labelOptions]
  );

  async function review(row: HistoryRow, status: ReviewStatus) {
    if (!onReviewLabel) return;
    const label = drafts[row.id] || row.display_label || "";
    setReviewingId(row.id);
    try {
      await onReviewLabel(row, label, status);
    } finally {
      setReviewingId(null);
    }
  }

  return (
    <section className="panel history-review-panel">
      <div className="history-review-toolbar">
        <label>
          Trạng thái nhãn
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">Tất cả</option>
            <option value="needs_review">Cần duyệt</option>
            <option value="human_verified">Admin đã duyệt</option>
            <option value="metadata_verified">Metadata xác minh</option>
            <option value="model_inferred">AI suy ra</option>
            <option value="no_evidence">Không đủ bằng chứng</option>
          </select>
        </label>
        <span>{visibleRows.length}/{rows.length} bản ghi</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Thời gian</th>
              <th>Tên vật</th>
              <th>Lớp AI gốc</th>
              <th>Trạng thái nhãn</th>
              <th>Nhóm / thùng</th>
              <th>Độ tin cậy</th>
              <th>Ảnh</th>
              {onReviewLabel ? <th>Duyệt nhãn</th> : null}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr key={row.id}>
                <td>{row.id}</td>
                <td>{row.ts}</td>
                <td>{row.display_label || "Chưa xác định vật"}</td>
                <td>{row.cls_name}</td>
                <td>
                  <span className={`history-label-status history-label-status-${row.label_status || "unknown"}`}>
                    {STATUS_LABELS[row.label_status || ""] || "Chưa chuẩn hóa"}
                  </span>
                </td>
                <td>{row.route_label || "-"} / {row.bin_index ?? "-"}</td>
                <td>{Math.round(row.conf * 1000) / 10}%</td>
                <td>
                  {row.annotated_path || row.image_path ? (
                    <button
                      className="secondary-button compact-button history-image-link"
                      onClick={() =>
                        void (onOpenImage
                          ? onOpenImage(row)
                          : openAgentBlob(historyImagePath(row.id, "annotated"), imageToken))
                      }
                      type="button"
                    >
                      <Camera size={15} />
                      <span>Mở ảnh</span>
                    </button>
                  ) : (
                    "-"
                  )}
                </td>
                {onReviewLabel ? (
                  <td>
                    <div className="history-review-actions">
                      <select
                        aria-label={`Nhãn cho bản ghi ${row.id}`}
                        value={drafts[row.id] ?? row.display_label ?? ""}
                        onChange={(event) =>
                          setDrafts((current) => ({ ...current, [row.id]: event.target.value }))
                        }
                      >
                        <option value="">Chọn tên vật…</option>
                        {options.map((label) => <option key={label} value={label}>{label}</option>)}
                      </select>
                      <button
                        className="secondary-button compact-button"
                        disabled={reviewingId === row.id || !(drafts[row.id] || row.display_label)}
                        onClick={() => void review(row, "human_verified")}
                        type="button"
                      >
                        <Check size={14} /> Xác nhận
                      </button>
                      <button
                        className="secondary-button compact-button"
                        disabled={reviewingId === row.id}
                        onClick={() => void review(row, "no_evidence")}
                        type="button"
                      >
                        <CircleHelp size={14} /> Không đủ ảnh
                      </button>
                    </div>
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!visibleRows.length ? <div className="empty-state">Chưa có lịch sử phù hợp bộ lọc.</div> : null}
    </section>
  );
}
