"use client";

import { Download } from "lucide-react";

import { AGENT_URL } from "@/lib/agent";
import type { DatasetSummary, HistoryRow, SourceQuality } from "@/lib/agent";

import { HistoryPanel } from "@/components/primitives/history-panel";

function MetricCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="metric-card">
      <span className="eyebrow">{label}</span>
      <strong>{value}</strong>
      <small>{detail || "-"}</small>
    </div>
  );
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

function adminHistoryExportUrl(token: string) {
  const url = new URL(`${AGENT_URL}/api/history/export.csv`);
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

type AdminReportsPanelProps = {
  history: HistoryRow[];
  sourceQuality: SourceQuality | null;
  summary: DatasetSummary | null;
  token: string;
};

export function AdminReportsPanel({
  history,
  sourceQuality,
  summary,
  token
}: AdminReportsPanelProps) {
  const exportHref = adminHistoryExportUrl(token);
  const topClasses = Object.entries(summary?.classes ?? {})
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 8);
  const priorityIssues =
    sourceQuality?.classes
      .filter((item) => item.source_issue_count || item.missing_for_strong_train)
      .slice(0, 8) ?? [];
  return (
    <section className="content-grid admin-reports-grid">
      <div className="stat-row">
        <MetricCard label="Dòng lịch sử" value={formatNumber(history.length)} detail="Đang hiển thị gần đây" />
        <MetricCard label="Ảnh dataset" value={formatNumber(summary?.images ?? 0)} detail="Hàng đợi training" />
        <MetricCard label="Boxes" value={formatNumber(summary?.boxes ?? 0)} detail="BBox đã index" />
        <MetricCard
          label="Lỗi nguồn"
          value={formatNumber(sourceQuality?.invalid_source_images ?? 0)}
          detail="Nguồn cần kiểm tra"
        />
      </div>
      <div className="panel report-export-panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Báo cáo vận hành</span>
            <strong>Export lịch sử và chất lượng nguồn</strong>
          </div>
          <a className="primary-button" href={exportHref}>
            <Download size={17} />
            <span>Tải CSV Admin</span>
          </a>
        </div>
        <p className="muted-copy">
          CSV Admin giữ đủ trường vận hành hiện có để audit nội bộ. User export riêng chỉ trả
          các cột an toàn, không có path ảnh.
        </p>
      </div>
      <div className="panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Top class</span>
            <strong>Phân bố dataset</strong>
          </div>
        </div>
        <div className="class-list">
          {topClasses.length ? (
            topClasses.map(([name, count]) => (
              <div className="class-row" key={name}>
                <span>{name}</span>
                <strong>{formatNumber(Number(count))}</strong>
              </div>
            ))
          ) : (
            <div className="empty-state">Chưa có dataset summary.</div>
          )}
        </div>
      </div>
      <div className="panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Chất lượng nguồn</span>
            <strong>Class cần ưu tiên</strong>
          </div>
        </div>
        <div className="class-list">
          {priorityIssues.length ? (
            priorityIssues.map((item) => (
              <div className="class-row" key={item.class_name}>
                <span>
                  {item.class_name}
                  <small>{item.priority}</small>
                </span>
                <strong>{formatNumber(item.source_issue_count + item.missing_for_strong_train)}</strong>
              </div>
            ))
          ) : (
            <div className="empty-state">Chưa có cảnh báo source quality.</div>
          )}
        </div>
      </div>
      <HistoryPanel imageToken={token} rows={history.slice(0, 10)} />
    </section>
  );
}
