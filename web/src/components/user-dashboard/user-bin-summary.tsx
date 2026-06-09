"use client";

import { Trash2 } from "lucide-react";

import type { UserAnalytics } from "@/lib/agent";

export function UserBinSummary({ analytics }: { analytics: UserAnalytics | null }) {
  return (
    <div className="stat-row user-bin-row">
      {(analytics?.bins ?? fallbackBins()).map((bin) => (
        <div className="metric-card bin-fill-card" key={bin.bin_index}>
          <div className="metric-icon">
            <Trash2 size={18} />
          </div>
          <span>Thùng {bin.bin_index}</span>
          <strong>{bin.percent}%</strong>
          <div className="fill-meter" aria-label={`Thùng ${bin.bin_index} đầy ${bin.percent}%`}>
            <span style={{ width: `${bin.percent}%` }} />
          </div>
          <small>
            {bin.label}
            {bin.stale ? " - dữ liệu cũ" : ""}
          </small>
        </div>
      ))}
    </div>
  );
}

function fallbackBins() {
  return [1, 2, 3].map((binIndex) => ({
    bin_index: binIndex,
    label: `Thùng ${binIndex}`,
    percent: 0,
    updated_at: null,
    stale: true
  }));
}
