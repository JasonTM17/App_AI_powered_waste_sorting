"use client";

import { FileDown } from "lucide-react";

import type { UserReport } from "@/lib/agent";
import { userHistoryExportUrl } from "@/lib/agent";

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
        <a className="primary-button" href={userHistoryExportUrl(report?.range_days ?? 30, imageToken)}>
          <FileDown size={17} />
          <span>Tải CSV User</span>
        </a>
        <div className="safe-field-list">
          {(report?.csv_safe_fields ?? []).map((field) => (
            <span key={field}>{field}</span>
          ))}
        </div>
      </section>
    </>
  );
}
