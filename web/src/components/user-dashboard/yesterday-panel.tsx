"use client";

import { Clock3 } from "lucide-react";
import { UserAnalytics } from "@/lib/agent";

export function YesterdayPanel({ analytics }: { analytics: UserAnalytics | null }) {
  const yesterday = analytics?.yesterday;
  return (
    <section className="user-panel">
      <div className="user-panel-heading inline">
        <div>
          <span className="eyebrow">Hôm qua</span>
          <strong>Bạn đã bỏ gì?</strong>
        </div>
        <Clock3 size={20} />
      </div>
      <div className="yesterday-total">
        <strong>{yesterday?.total ?? 0}</strong>
        <span>lượt ghi nhận ngày {formatDate(yesterday?.date)}</span>
      </div>
      <div className="class-list user-class-list">
        {yesterday?.top_classes.length ? (
          yesterday.top_classes.map((item) => (
            <div className="class-row" key={item.cls_name}>
              <span>
                {item.cls_name}
                {item.route_label ? ` · ${item.route_label}` : ""}
              </span>
              <strong>{item.count}</strong>
            </div>
          ))
        ) : (
          <div className="empty-state">Hôm qua chưa có rác nào được ghi nhận.</div>
        )}
      </div>
    </section>
  );
}

function formatDate(value?: string) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit" }).format(date);
}
