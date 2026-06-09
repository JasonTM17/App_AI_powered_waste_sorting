"use client";

import { UserAnalytics } from "@/lib/agent";
import { AnalyticsMetrics } from "./analytics-metrics";
import { CompositionPanel, UserStackedBars, UserTimelineChart } from "./user-svg-charts";
import { YesterdayPanel } from "./yesterday-panel";

export function UserAnalyticsContent({ analytics }: { analytics: UserAnalytics | null }) {
  return (
    <>
      <AnalyticsMetrics analytics={analytics} />
      <section className="user-analytics-grid">
        <UserTimelineChart analytics={analytics} />
        <CompositionPanel analytics={analytics} />
        <UserStackedBars analytics={analytics} />
        <YesterdayPanel analytics={analytics} />
      </section>
    </>
  );
}

