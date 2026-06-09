"use client";

import { Activity, Gauge, MapPin, Server, Signal } from "lucide-react";

import type { UserAnalytics } from "@/lib/agent";

const statusLabels: Record<string, string> = {
  online: "Đang hoạt động",
  warning: "Cần chú ý",
  offline: "Ngoại tuyến"
};

export function UserStatusPanels({ analytics }: { analytics: UserAnalytics | null }) {
  const eco = analytics?.eco_score;
  const device = analytics?.device_status;
  return (
    <section className="user-status-grid">
      <div className="user-panel eco-score-panel">
        <div className="user-panel-heading inline">
          <div>
            <span className="eyebrow">Eco Score</span>
            <strong>{eco?.label || "Đang tính"}</strong>
          </div>
          <Gauge size={22} />
        </div>
        <div className="eco-score-ring" aria-label={`Eco Score ${eco?.score ?? 0}`}>
          <span>{eco?.score ?? 0}</span>
        </div>
        <div className="eco-breakdown">
          <span>Tái chế {Math.round(eco?.recyclable_rate ?? 0)}%</span>
          <span>Hữu cơ {Math.round(eco?.organic_rate ?? 0)}%</span>
          <span>Vô cơ {Math.round(eco?.inorganic_rate ?? 0)}%</span>
        </div>
      </div>

      <div className="user-panel device-status-panel">
        <div className="user-panel-heading inline">
          <div>
            <span className="eyebrow">Thiết bị</span>
            <strong>{device?.device_name || "Trash Sorter"}</strong>
          </div>
          <Server size={22} />
        </div>
        <div className={`device-status-badge ${device?.status ?? "offline"}`}>
          <Signal size={16} />
          <span>{statusLabels[device?.status ?? "offline"] ?? device?.status ?? "offline"}</span>
        </div>
        <div className="device-detail-list">
          <span>
            <MapPin size={15} />
            {device?.location || "Trạm local"}
          </span>
          <span>
            <Activity size={15} />
            {device?.message || "Chưa có trạng thái thiết bị"}
          </span>
        </div>
      </div>
    </section>
  );
}
