"use client";

import { StatusPill } from "@/components/primitives/status-pill";

type DeviceListProps = {
  rows: Array<Record<string, unknown>>;
  empty: string;
};

export function DeviceList({ rows, empty }: DeviceListProps) {
  if (!rows.length) {
    return <div className="empty-state">{empty}</div>;
  }
  return (
    <div className="device-list">
      {rows.map((row, index) => {
        const isUsb = Boolean(row.is_usb || row.is_external);
        return (
          <div className={isUsb ? "device-row" : "device-row disabled"} key={index}>
            <strong>{String(row.name || row.device || "Device")}</strong>
            <span>{String(row.hwid || row.instance_id || "")}</span>
            <StatusPill ok={isUsb} text={isUsb ? "USB" : "Đã khóa"} />
          </div>
        );
      })}
    </div>
  );
}
