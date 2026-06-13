"use client";

import type { AuthMe, UserAnalytics } from "@/lib/agent";
import { StitchMetricIcon } from "./stitch-user-overview";

export function UserHeroSummary({
  analytics,
  auth,
  busy
}: {
  analytics: UserAnalytics | null;
  auth: AuthMe | null;
  busy: boolean;
}) {
  const username = auth?.username || "User";
  const recyclableRate = routePercent(analytics, "I");
  return (
    <section className="user-hero-summary" aria-label="Tổng quan nhật ký rác">
      <div className="user-hero-copy">
        <span className="eyebrow">Trash Sorter Pro</span>
        <h1>Xin chào, {username}</h1>
        <p>Nhật ký rác của bạn được tổng hợp từ thiết bị EcoSort local.</p>
      </div>
      <div className="stitch-kpi-row">
        <HeroStat
          detail={analytics ? `${analytics.today_total} lượt hôm nay` : "Đang tải dữ liệu"}
          icon="total"
          label="Tổng lượt phân loại"
          suffix="lượt"
          value={analytics?.total ?? 0}
        />
        <HeroStat
          detail={analytics ? "Tỷ lệ rác tái chế" : "Đang tính"}
          icon="recycle"
          label="Tỷ lệ tái chế"
          suffix="%"
          value={Math.round(recyclableRate)}
        />
        <HeroStat
          detail="Độ tin cậy trung bình"
          icon="confidence"
          label="Độ tin cậy AI"
          suffix="%"
          value={Math.round((analytics?.average_confidence ?? 0) * 100)}
        />
        <HeroStat
          detail={busy ? "Đang tải" : analytics?.eco_score.label || "Cần theo dõi"}
          icon="score"
          label="Eco Score"
          suffix="/100"
          value={analytics?.eco_score.score ?? 0}
        />
      </div>
    </section>
  );
}

function HeroStat({
  detail,
  icon,
  label,
  suffix,
  value
}: {
  detail: string;
  icon: "total" | "recycle" | "confidence" | "score";
  label: string;
  suffix: string;
  value: number | string;
}) {
  return (
    <div className="user-hero-stat">
      <div className="stitch-stat-top">
        <small>{label}</small>
        <span>
          <StitchMetricIcon kind={icon} />
        </span>
      </div>
      <strong>
        {typeof value === "number" ? new Intl.NumberFormat("vi-VN").format(value) : value}
        <em>{suffix}</em>
      </strong>
      <p>{detail}</p>
    </div>
  );
}

function routePercent(analytics: UserAnalytics | null, command: "O" | "R" | "I") {
  return analytics?.route_totals.find((item) => item.command === command)?.percent ?? 0;
}
