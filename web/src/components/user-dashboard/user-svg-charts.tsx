"use client";

import { UserAnalytics, UserDailyWaste } from "@/lib/agent";

const routeColors: Record<string, string> = {
  O: "#16a34a",
  R: "#ef6c00",
  I: "#005faf"
};

export function UserTimelineChart({ analytics }: { analytics: UserAnalytics | null }) {
  const rows = analytics?.daily ?? [];
  const hasData = rows.some((item) => item.total > 0);
  const maxValue = Math.max(1, ...rows.map((item) => item.total));
  const points = rows.map((item, index) => {
    const x = rows.length <= 1 ? 24 : 24 + (index / (rows.length - 1)) * 512;
    const y = 168 - (item.total / maxValue) * 132;
    return `${x},${y}`;
  });
  const area = points.length ? `M24,180 L${points.join(" L")} L536,180 Z` : "M24,180 L536,180 Z";
  return (
    <section className="user-panel user-chart-panel">
      <div className="user-panel-heading">
        <span className="eyebrow">Xu hướng</span>
        <strong>Lượt bỏ rác theo ngày</strong>
      </div>
      <div className="chart-frame">
        <svg className="user-line-chart" role="img" viewBox="0 0 560 204" aria-label={timelineSummary(rows)}>
          <path className="chart-grid" d="M24 36H536M24 80H536M24 124H536M24 168H536" />
          <path className="chart-area" d={area} />
          <polyline className="chart-line" fill="none" points={points.join(" ")} />
          {rows.map((item, index) => {
            const x = rows.length <= 1 ? 24 : 24 + (index / (rows.length - 1)) * 512;
            const y = 168 - (item.total / maxValue) * 132;
            return (
              <circle
                className="chart-dot"
                cx={x}
                cy={y}
                key={item.date}
                r={index % 3 === 0 ? 3.8 : 2.6}
              >
                <title>{`${item.date}: ${item.total} lượt`}</title>
              </circle>
            );
          })}
        </svg>
        {!analytics ? <ChartEmpty text="Đang tải dữ liệu biểu đồ..." /> : null}
        {analytics && !hasData ? <ChartEmpty text="Chưa có lượt bỏ rác trong khoảng này." /> : null}
      </div>
      <div className="chart-axis-row">
        <span>{rows[0]?.date ?? "-"}</span>
        <span>{rows.at(-1)?.date ?? "-"}</span>
      </div>
    </section>
  );
}

export function UserStackedBars({ analytics }: { analytics: UserAnalytics | null }) {
  const rows = (analytics?.range_days ?? 0) >= 90 ? analytics?.monthly ?? [] : analytics?.daily ?? [];
  const visibleRows = rows.slice(-14);
  const hasData = visibleRows.some((item) => item.total > 0);
  const maxValue = Math.max(1, ...visibleRows.map((item) => item.total));
  return (
    <section className="user-panel user-chart-panel">
      <div className="user-panel-heading">
        <span className="eyebrow">{(analytics?.range_days ?? 0) >= 90 ? "Theo tháng" : "Theo ngày"}</span>
        <strong>Cơ cấu 3 thùng</strong>
      </div>
      <div className="chart-frame stacked-frame">
        <div className="stacked-chart" role="img" aria-label="Biểu đồ cột hữu cơ, vô cơ và tái chế">
          {visibleRows.map((item) => {
            const height = Math.max(6, (item.total / maxValue) * 150);
            const organicHeight = item.total ? (item.organic / item.total) * height : 0;
            const inorganicHeight = item.total ? (item.inorganic / item.total) * height : 0;
            const recyclableHeight = item.total ? (item.recyclable / item.total) * height : 0;
            return (
              <div className="stacked-bar-wrap" key={"date" in item ? item.date : item.month}>
                <div className="stacked-bar" title={`${barLabel(item)}: ${item.total} lượt`}>
                  <span className="bar-organic" style={{ height: organicHeight }} />
                  <span className="bar-inorganic" style={{ height: inorganicHeight }} />
                  <span className="bar-recyclable" style={{ height: recyclableHeight }} />
                </div>
                <small>{shortLabel(barLabel(item))}</small>
              </div>
            );
          })}
        </div>
        {!analytics ? <ChartEmpty text="Đang tải cơ cấu 3 thùng..." /> : null}
        {analytics && !hasData ? <ChartEmpty text="Chưa có dữ liệu để dựng cột." /> : null}
      </div>
      <ChartLegend />
    </section>
  );
}

export function CompositionPanel({ analytics }: { analytics: UserAnalytics | null }) {
  const routes = analytics?.route_totals ?? [];
  return (
    <section className="user-panel">
      <div className="user-panel-heading">
        <span className="eyebrow">Thành phần</span>
        <strong>Rác của bạn vào thùng nào</strong>
      </div>
      <div className="composition-list">
        {routes.length ? (
          routes.map((item) => (
            <div className="composition-row" key={item.command}>
              <div>
                <span className="route-dot" style={{ background: routeColors[item.command] }} />
                <strong>{item.route_label}</strong>
                <small>Thùng {item.bin_index}</small>
              </div>
              <span>{item.count} lượt</span>
              <div className="composition-meter">
                <i style={{ background: routeColors[item.command], width: `${item.percent}%` }} />
              </div>
              <b>{Math.round(item.percent)}%</b>
            </div>
          ))
        ) : (
          <div className="empty-state">Chưa có thành phần rác trong khoảng này.</div>
        )}
      </div>
    </section>
  );
}

function ChartLegend() {
  return (
    <div className="chart-legend">
      <span>
        <i style={{ background: routeColors.O }} />
        Hữu cơ
      </span>
      <span>
        <i style={{ background: routeColors.R }} />
        Vô cơ
      </span>
      <span>
        <i style={{ background: routeColors.I }} />
        Tái chế
      </span>
    </div>
  );
}

function ChartEmpty({ text }: { text: string }) {
  return <div className="chart-empty">{text}</div>;
}

function timelineSummary(rows: UserDailyWaste[]) {
  const total = rows.reduce((sum, item) => sum + item.total, 0);
  return `Biểu đồ đường ${rows.length} mốc ngày, tổng ${total} lượt bỏ rác`;
}

function barLabel(item: { date?: string; month?: string }) {
  return item.date ?? item.month ?? "-";
}

function shortLabel(value: string) {
  if (value.includes("-")) {
    const parts = value.split("-");
    return parts.length === 3 ? parts[2] : parts.slice(-1)[0];
  }
  return value;
}
