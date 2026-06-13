"use client";

import { FileDown } from "lucide-react";

import type { UserReport } from "@/lib/agent";
import { downloadAgentBlob, userHistoryExportPath } from "@/lib/agent";

type UserReportScreenProps = {
  imageToken: string;
  report: UserReport | null;
};

export function UserReportScreen({ imageToken, report }: UserReportScreenProps) {
  return (
    <>
      <div className="user-report-grid">
        {(report?.summary_cards ?? []).map((card) => (
          <article className={`user-report-card ${card.tone}`} key={card.title}>
            <span>{card.title}</span>
            <strong>{card.value}</strong>
            <small>{card.detail}</small>
          </article>
        ))}
      </div>
      <section className="user-panel report-export-panel">
        <div className="user-panel-heading inline">
          <div>
            <span className="eyebrow">Xuất dữ liệu</span>
            <strong>CSV an toàn cho người dùng</strong>
          </div>
          <FileDown size={21} />
        </div>
        <p>File export chỉ gồm các cột tổng hợp theo tài khoản, không có đường dẫn ảnh hoặc log thô.</p>
        <button
          className="primary-button"
          onClick={() =>
            void downloadAgentBlob(
              userHistoryExportPath(report?.range_days ?? 30),
              `ecosort-user-history-${report?.range_days ?? 30}d.csv`,
              imageToken
            )
          }
          type="button"
        >
          <FileDown size={17} />
          <span>Tải CSV User</span>
        </button>
        <div className="safe-field-list">
          {(report?.csv_safe_fields ?? []).map((field) => (
            <span key={field}>{field}</span>
          ))}
        </div>
      </section>
    </>
  );
}
