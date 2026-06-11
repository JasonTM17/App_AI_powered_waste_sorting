"use client";

import { AlertTriangle, CheckCircle2, ShieldCheck, Square } from "lucide-react";

import type { ActuationTestMode } from "@/lib/agent";
import { StatusPill } from "@/components/primitives/status-pill";

type ActuationTestModePanelProps = {
  busy: boolean;
  mode: ActuationTestMode | null;
  onToggle: (enabled: boolean) => void;
};

export function ActuationTestModePanel({
  busy,
  mode,
  onToggle
}: ActuationTestModePanelProps) {
  const enabled = Boolean(mode?.enabled);
  const warning = mode?.warning || "";
  return (
    <div className="panel full-span">
      <div className="panel-toolbar no-pad">
        <div>
          <span className="eyebrow">Actuation Test Mode</span>
          <strong>{enabled ? "Đang bật" : "Đang tắt"}</strong>
          <p className="muted">{"Kiem chung camera -> group -> bin -> payload -> ACK -> history."}</p>
        </div>
        <button
          className={enabled ? "danger-button" : "primary-button"}
          disabled={busy}
          onClick={() => onToggle(!enabled)}
          type="button"
        >
          {enabled ? <Square size={17} /> : <ShieldCheck size={17} />}
          <span>{enabled ? "Tắt test mode" : "Bật test mode"}</span>
        </button>
      </div>
      {warning ? (
        <div className="capture-warning">
          <AlertTriangle size={16} />
          <span>{warning}</span>
        </div>
      ) : (
        <div className="success">
          <CheckCircle2 size={16} />
          <span>UART connected, san sang ghi nhan ACK khi co dispatch.</span>
        </div>
      )}
      <div className="device-list">
        {(mode?.evidence ?? []).map((item) => (
          <div className="device-row" key={item.history_id}>
            <strong>
              #{item.history_id} {item.detected_class} - {Math.round(item.confidence * 100)}%
            </strong>
            <span>
              {[
                item.route_label || "-",
                `bin ${item.bin_index || "-"}`,
                `cmd ${item.command || "-"}`,
                `payload ${(item.serial_payload || "-").trim()}`,
                item.uart_sent ? "UART sent" : "UART not sent",
                item.ack_status || "-",
                item.timestamp
              ].join(" -> ")}
            </span>
            <StatusPill ok={item.ack_status === "ok"} text={item.ack_status || "pending"} />
          </div>
        ))}
      </div>
      {mode && !mode.evidence.length ? (
        <div className="empty-state">Chưa có evidence. Bật camera live và đưa từng loại rác vào vùng nhận diện.</div>
      ) : null}
    </div>
  );
}
