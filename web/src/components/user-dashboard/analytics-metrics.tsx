"use client";

import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight, Gauge, Recycle, Trophy, TrendingUp } from "lucide-react";
import { UserAnalytics } from "@/lib/agent";

export function AnalyticsMetrics({ analytics }: { analytics: UserAnalytics | null }) {
  const topClass = analytics?.top_classes[0];
  const recyclable = analytics?.route_totals.find((item) => item.command === "I");
  const delta = analytics?.comparison.delta ?? 0;
  const DeltaIcon = delta >= 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <section className="user-metric-grid" aria-label="Tổng quan rác đã bỏ">
      <MetricCard
        accent="accent-green"
        icon={<Recycle size={18} />}
        label="Tổng lượt bỏ rác"
        value={formatNumber(analytics?.total ?? 0)}
        detail={analytics ? `${analytics.range_days} ngày gần đây` : "Đang tải dữ liệu"}
      />
      <MetricCard
        accent="accent-slate"
        icon={<Gauge size={18} />}
        label="Eco Score"
        value={String(analytics?.eco_score.score ?? 0)}
        detail={analytics?.eco_score.label || "Đang tính điểm"}
      />
      <MetricCard
        accent="accent-blue"
        icon={<Trophy size={18} />}
        label="Loại nhiều nhất"
        value={topClass?.cls_name ?? "-"}
        detail={topClass ? `${topClass.count} lượt, ${topClass.percent}%` : "Chưa có mẫu nổi bật"}
      />
      <MetricCard
        accent="accent-orange"
        icon={<TrendingUp size={18} />}
        label="Tỷ lệ tái chế"
        value={`${Math.round(recyclable?.percent ?? 0)}%`}
        detail={recyclable ? `${recyclable.count} lượt vào thùng ${recyclable.bin_index}` : "Chưa có dữ liệu"}
      />
      <MetricCard
        accent="accent-slate"
        icon={<DeltaIcon size={18} />}
        label="So với kỳ trước"
        value={delta >= 0 ? `+${delta}` : String(delta)}
        detail={analytics ? `${analytics.comparison.delta_percent}% thay đổi` : "Đang tính"}
      />
    </section>
  );
}

function MetricCard({
  accent,
  icon,
  label,
  value,
  detail
}: {
  accent: string;
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className={`user-metric-card ${accent}`}>
      <div className="metric-icon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("vi-VN").format(Math.round(value));
}
