"use client";

import { ArrowDownRight, BarChart3, Clock, Leaf, Recycle, Scale, Sparkles, Trash2 } from "lucide-react";

import type { UserAnalytics, UserHistoryItem } from "@/lib/agent";

const categoryLabels: Record<UserHistoryItem["category"], string> = {
  organic: "Hữu cơ",
  inorganic: "Vô cơ",
  recyclable: "Tái chế"
};

export function StitchUserOverview({
  analytics,
  history
}: {
  analytics: UserAnalytics | null;
  history: UserHistoryItem[];
}) {
  const advice = analytics?.advice[0] ?? analytics?.insights[0];
  return (
    <>
      <section className="stitch-dashboard-main">
        <DailyWasteBars analytics={analytics} />
        <div className="stitch-side-column">
          <AdviceCard
            title={advice?.title || "Lời khuyên cho bạn"}
            message={
              advice?.message ||
              "Khi có thêm dữ liệu, EcoPet sẽ gợi ý cách tăng tỷ lệ tái chế và giảm rác dùng một lần."
            }
          />
          <BinStatusCard analytics={analytics} />
        </div>
      </section>
      <RecentClassifications rows={history} />
    </>
  );
}

function DailyWasteBars({ analytics }: { analytics: UserAnalytics | null }) {
  const rows = analytics?.daily.slice(-7) ?? [];
  const maxValue = Math.max(1, ...rows.map((row) => row.total));
  return (
    <section className="user-panel stitch-chart-card">
      <div className="user-panel-heading inline">
        <div>
          <span className="eyebrow">Lượng rác hằng ngày</span>
          <strong>Lượng rác theo ngày</strong>
        </div>
        <BarChart3 size={21} />
      </div>
      <div className="stitch-bar-chart" role="img" aria-label={chartSummary(rows)}>
        {rows.length ? (
          rows.map((row, index) => {
            const height = Math.max(10, (row.total / maxValue) * 188);
            return (
              <div className="stitch-bar-item" key={row.date}>
                <div className={index === 2 ? "stitch-bar active" : "stitch-bar"} style={{ height }}>
                  <span>{row.total}</span>
                </div>
                <small>{shortDate(row.date)}</small>
              </div>
            );
          })
        ) : (
          <div className="chart-empty">Đang tải biểu đồ rác theo ngày...</div>
        )}
      </div>
    </section>
  );
}

function AdviceCard({ title, message }: { title: string; message: string }) {
  return (
    <section className="stitch-advice-card">
      <div className="stitch-advice-heading">
        <Leaf size={18} />
        <strong>{title}</strong>
      </div>
      <p>{message}</p>
      <span className="stitch-advice-action">Gợi ý được tạo từ lịch sử rác của bạn</span>
    </section>
  );
}

function BinStatusCard({ analytics }: { analytics: UserAnalytics | null }) {
  const bins = analytics?.bins ?? [];
  return (
    <section className="user-panel stitch-bin-card">
      <div className="user-panel-heading inline">
        <div>
          <span className="eyebrow">Thiết bị</span>
          <strong>Trạng thái thùng</strong>
        </div>
        <Trash2 size={20} />
      </div>
      <div className="stitch-bin-list">
        {bins.length ? (
          bins.map((bin) => (
            <div className="stitch-bin-row" key={bin.bin_index}>
              <span>{bin.label || `Thùng ${bin.bin_index}`}</span>
              <div className="composition-meter">
                <i style={{ width: `${bin.percent}%` }} />
              </div>
              <strong>{bin.percent}%</strong>
            </div>
          ))
        ) : (
          <div className="empty-state">Chưa có dữ liệu thùng.</div>
        )}
      </div>
    </section>
  );
}

function RecentClassifications({ rows }: { rows: UserHistoryItem[] }) {
  return (
    <section className="user-panel stitch-recent-card">
      <div className="user-panel-heading inline">
        <div>
          <span className="eyebrow">Phân loại gần đây</span>
          <strong>Phân loại gần đây</strong>
        </div>
        <Clock size={21} />
      </div>
      <div className="stitch-recent-table">
        <div className="stitch-table-head">
          <span>Vật phẩm</span>
          <span>Nhóm</span>
          <span>AI</span>
          <span>Giờ</span>
        </div>
        {rows.length ? (
          rows.slice(0, 6).map((row) => (
            <div className="stitch-table-row" key={row.id}>
              <div className="stitch-item-cell">
                <span className="stitch-item-thumb">
                  <Recycle size={14} />
                </span>
                <strong>{row.cls_name || "Chưa rõ"}</strong>
              </div>
              <span className={`stitch-category-chip ${row.category}`}>{categoryLabels[row.category]}</span>
              <span className="stitch-confidence">
                {Math.round(row.confidence * 100)}%
                <i />
              </span>
              <span>{formatTime(row.ts)}</span>
            </div>
          ))
        ) : (
          <div className="empty-state">Chưa có lịch sử thuộc tài khoản này.</div>
        )}
      </div>
    </section>
  );
}

export function StitchMetricIcon({ kind }: { kind: "total" | "recycle" | "confidence" | "score" }) {
  if (kind === "total") {
    return <Scale size={18} />;
  }
  if (kind === "recycle") {
    return <Recycle size={18} />;
  }
  if (kind === "confidence") {
    return <Sparkles size={18} />;
  }
  return <ArrowDownRight size={18} />;
}

function chartSummary(rows: Array<{ date: string; total: number }>) {
  const total = rows.reduce((sum, row) => sum + row.total, 0);
  return `Biểu đồ cột lượng rác 7 ngày, tổng ${total} lượt`;
}

function shortDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value.slice(-5) || "-";
  }
  return new Intl.DateTimeFormat("vi-VN", { weekday: "short" }).format(date);
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" }).format(date);
}
