"use client";

import { CalendarDays } from "lucide-react";
import { AnalyticsRangeDays } from "@/lib/agent";

const rangeOptions: Array<{ value: AnalyticsRangeDays; label: string }> = [
  { value: 7, label: "7 ngày" },
  { value: 30, label: "30 ngày" },
  { value: 90, label: "90 ngày" },
  { value: 180, label: "180 ngày" }
];

export function RangeSelector({
  rangeDays,
  onRangeChange
}: {
  rangeDays: AnalyticsRangeDays;
  onRangeChange: (value: AnalyticsRangeDays) => void;
}) {
  return (
    <div className="user-range-control" aria-label="Chọn khoảng thời gian">
      <CalendarDays size={18} />
      {rangeOptions.map((item) => (
        <button
          aria-pressed={rangeDays === item.value}
          className={rangeDays === item.value ? "active" : ""}
          key={item.value}
          onClick={() => onRangeChange(item.value)}
          type="button"
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
