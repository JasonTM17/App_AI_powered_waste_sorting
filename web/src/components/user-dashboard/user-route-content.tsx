"use client";

import { AiAdvisorPanel } from "./ai-advisor-panel";
import {
  UserAlertsScreen,
  UserDeviceIssueScreen,
  UserMapScreen,
  UserScheduleScreen
} from "@/components/operations-panels";
import { UserAccountScreen } from "./user-account-screen";
import { UserAnalyticsContent } from "./user-analytics-content";
import { UserBinSummary } from "./user-bin-summary";
import type { UserDashboardPanelProps } from "./user-dashboard-types";
import { UserDeviceScreen } from "./user-device-screen";
import {
  ExperienceChallenges,
  UserCommunityScreen,
  UserLeaderboardScreen,
  UserNotificationScreen
} from "./user-experience-screens";
import { UserHistoryPanel } from "./user-history-panel";
import { UserReportScreen } from "./user-report-screen";
import { UserStatusPanels } from "./user-status-panels";
import { StitchUserOverview } from "./stitch-user-overview";

export function UserRouteContent(props: UserDashboardPanelProps) {
  const { analytics, device, experience, history, imageToken, report, view } = props;
  if (view === "history") {
    return <UserHistoryPanel imageToken={imageToken} rows={history} />;
  }
  if (view === "device") {
    return <UserDeviceScreen analytics={analytics} device={device} history={history} imageToken={imageToken} />;
  }
  if (view === "map") {
    return <UserMapScreen busy={props.busy} map={props.binMap} onRefresh={props.onRefreshOperations} />;
  }
  if (view === "alerts") {
    return <UserAlertsScreen alerts={props.operationAlerts} />;
  }
  if (view === "schedule") {
    return (
      <UserScheduleScreen
        busy={props.busy}
        schedules={props.operationSchedules}
        onCompleteCollection={props.onCompleteCollection}
      />
    );
  }
  if (view === "collect") {
    return (
      <UserScheduleScreen
        collectOnly
        busy={props.busy}
        schedules={props.operationSchedules}
        onCompleteCollection={props.onCompleteCollection}
      />
    );
  }
  if (view === "report-issue") {
    return (
      <UserDeviceIssueScreen
        busy={props.busy}
        map={props.binMap}
        onReportIssue={props.onReportDeviceIssue}
      />
    );
  }
  if (view === "analytics") {
    return (
      <>
        <UserAnalyticsContent analytics={analytics} />
        <ExperienceChallenges experience={experience} />
      </>
    );
  }
  if (view === "reports") {
    return <UserReportScreen imageToken={imageToken} report={report} />;
  }
  if (view === "notifications") {
    return <UserNotificationScreen experience={experience} />;
  }
  if (view === "community") {
    return <UserCommunityScreen experience={experience} />;
  }
  if (view === "leaderboard") {
    return <UserLeaderboardScreen experience={experience} />;
  }
  if (view === "account") {
    return <UserAccountScreen {...props} />;
  }
  if (view === "dashboard" || view === "ecopet") {
    return <StitchUserOverview analytics={analytics} history={history} />;
  }
  if (view === "advice") {
    return (
      <>
        <UserStatusPanels analytics={analytics} />
        <AdvisorBlock {...props} />
        <ExperienceChallenges experience={experience} />
      </>
    );
  }
  return (
    <>
      <UserBinSummary analytics={analytics} />
      <UserAnalyticsContent analytics={analytics} />
      <UserStatusPanels analytics={analytics} />
      <UserHistoryPanel imageToken={imageToken} rows={history} />
      <AdvisorBlock {...props} />
    </>
  );
}

function AdvisorBlock(props: UserDashboardPanelProps) {
  return (
    <AiAdvisorPanel
      advisor={props.advisor}
      analytics={props.analytics}
      busy={props.busy}
      question={props.advisorQuestion}
      rangeDays={props.rangeDays}
      onQuestionChange={props.onAdvisorQuestionChange}
      onRequest={props.onAdvisorRequest}
    />
  );
}
