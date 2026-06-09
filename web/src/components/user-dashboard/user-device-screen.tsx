"use client";

import type { UserAnalytics, UserDevice, UserHistoryItem } from "@/lib/agent";
import { UserBinSummary } from "./user-bin-summary";
import { UserHistoryPanel } from "./user-history-panel";
import { UserStatusPanels } from "./user-status-panels";

type UserDeviceScreenProps = {
  analytics: UserAnalytics | null;
  device: UserDevice | null;
  history: UserHistoryItem[];
  imageToken: string;
};

export function UserDeviceScreen({ analytics, device, history, imageToken }: UserDeviceScreenProps) {
  return (
    <>
      <UserStatusPanels analytics={analytics} />
      <UserBinSummary analytics={analytics} />
      <section className="user-panel device-owner-panel">
        <span className="eyebrow">Chủ thiết bị</span>
        <strong>{device?.owner_username || analytics?.device_status.owner_username || "Chưa cấu hình"}</strong>
        <p>{device?.device_status.message || analytics?.device_status.message || "Chưa có trạng thái thiết bị."}</p>
      </section>
      <UserHistoryPanel imageToken={imageToken} rows={device?.recent_activity ?? history.slice(0, 8)} />
    </>
  );
}
