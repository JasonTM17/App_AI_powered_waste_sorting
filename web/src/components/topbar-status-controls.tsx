"use client";

import { BrainCircuit, Camera, FileText, Play, Settings, Square, Video, Wifi } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { AGENT_URL, type AuthMe, type RuntimeStatus, type TrainingStatus } from "@/lib/agent";

type StatusPanel = "camera" | "model" | "agent";
type AdminTabTarget = "live" | "camera" | "data" | "logs" | "settings";

type TopbarStatusControlsProps = {
  agentError: string;
  auth: AuthMe | null;
  busy: boolean;
  status: RuntimeStatus | null;
  training: TrainingStatus | null;
  onCameraStart: () => void;
  onCameraStop: () => void;
  onNavigate: (tab: AdminTabTarget) => void;
  onRefresh: () => void;
};

export function TopbarStatusControls({
  agentError,
  auth,
  busy,
  status,
  training,
  onCameraStart,
  onCameraStop,
  onNavigate,
  onRefresh
}: TopbarStatusControlsProps) {
  const [open, setOpen] = useState<StatusPanel | null>(null);
  const panelId = useId();
  const toggle = (panel: StatusPanel) => setOpen((current) => (current === panel ? null : panel));
  const close = () => setOpen(null);
  const navigate = (tab: AdminTabTarget) => {
    onNavigate(tab);
    close();
  };

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, close]);

  return (
    <div className="status-action-group">
      <button
        aria-controls={`${panelId}-camera`}
        aria-expanded={open === "camera"}
        aria-label="Xem trạng thái Camera USB"
        className={open === "camera" ? "round-icon active" : "round-icon"}
        onClick={() => toggle("camera")}
        title="Camera USB"
        type="button"
      >
        <Video size={19} />
      </button>
      <button
        aria-controls={`${panelId}-model`}
        aria-expanded={open === "model"}
        aria-label="Xem trạng thái AI model"
        className={open === "model" ? "round-icon active" : "round-icon"}
        onClick={() => toggle("model")}
        title="AI model"
        type="button"
      >
        <BrainCircuit size={19} />
      </button>
      <button
        aria-controls={`${panelId}-agent`}
        aria-expanded={open === "agent"}
        aria-label="Xem trạng thái Local agent"
        className={open === "agent" ? "round-icon online active" : "round-icon online"}
        onClick={() => toggle("agent")}
        title="Local agent"
        type="button"
      >
        <Wifi size={19} />
      </button>

      {open ? (
        <section className="status-popover" id={`${panelId}-${open}`} role="dialog" aria-label={titleFor(open)}>
          <div className="status-popover-heading">
            <div>
              <span className="eyebrow">Trạng thái nhanh</span>
              <strong>{titleFor(open)}</strong>
            </div>
            <button className="icon-button icon-only" onClick={close} type="button" aria-label="Đóng trạng thái nhanh">
              ×
            </button>
          </div>
          {open === "camera" ? (
            <>
              <StatusRow label="Camera" value={status?.camera.running ? "Đang chạy" : "Đang tắt"} />
              <StatusRow label="Nguồn" value={status?.current_source || "Chưa chọn camera USB"} />
              <StatusRow label="Thiết bị USB" value={String(status?.usb_cameras.length ?? 0)} />
              <StatusRow label="FPS" value={formatNumber(status?.fps ?? 0)} />
              <StatusRow label="Backend" value={formatDiag(status?.camera_diagnostics?.backend) || "-"} />
              <StatusRow label="Mean" value={formatDiagNumber(status?.camera_diagnostics?.mean_brightness)} />
              <StatusRow label="Non-black" value={formatPercent(status?.camera_diagnostics?.non_black_ratio)} />
              <p>{formatStatusMessage(status?.camera.message) || "Camera chỉ dùng thiết bị USB ngoài."}</p>
              <div className="status-popover-actions">
                <button className="secondary-button compact-button" onClick={() => navigate("camera")} type="button">
                  <Camera size={15} />
                  <span>Mở camera</span>
                </button>
                {status?.camera.running ? (
                  <button className="danger-button compact-button" disabled={busy} onClick={onCameraStop} type="button">
                    <Square size={15} />
                    <span>Dừng</span>
                  </button>
                ) : (
                  <button className="primary-button compact-button" disabled={busy} onClick={onCameraStart} type="button">
                    <Play size={15} />
                    <span>Bật camera</span>
                  </button>
                )}
              </div>
            </>
          ) : null}
          {open === "model" ? (
            <>
              <StatusRow label="Model" value={status?.model.running ? "Sẵn sàng" : "Chưa sẵn sàng"} />
              <StatusRow label="Training" value={training?.running ? "Đang chạy" : "Đang tắt"} />
              <StatusRow label="Tiến độ" value={`${formatNumber(training?.progress_percent ?? 0)}%`} />
              <StatusRow label="3-Bin fallback" value={status?.three_bin_classifier.running ? "Đang bật" : "Đang tắt"} />
              <p>
                {formatStatusMessage(training?.message || status?.model.message) ||
                  "AI model dùng YOLO production và fallback 3 thùng khi cần."}
              </p>
              <div className="status-popover-actions">
                <button className="secondary-button compact-button" onClick={() => navigate("data")} type="button">
                  <BrainCircuit size={15} />
                  <span>Mở dữ liệu</span>
                </button>
                <button className="secondary-button compact-button" disabled={busy} onClick={onRefresh} type="button">
                  <span>Làm mới</span>
                </button>
              </div>
            </>
          ) : null}
          {open === "agent" ? (
            <>
              <StatusRow label="Agent" value={agentError ? "Offline" : "Online"} />
              <StatusRow label="URL" value={AGENT_URL} />
              <StatusRow label="UART" value={status?.uart.connected ? "Đã kết nối" : "Chưa kết nối"} />
              <StatusRow label="Phiên" value={auth?.session_expires_at ? `Hết hạn ${shortTime(auth.session_expires_at)}` : "Local"} />
              <p>
                {formatStatusMessage(agentError || status?.uart.message) ||
                  "Local agent đang xử lý camera, UART, dataset và quyền truy cập."}
              </p>
              <div className="status-popover-actions">
                <button className="secondary-button compact-button" onClick={() => navigate("logs")} type="button">
                  <FileText size={15} />
                  <span>Mở nhật ký</span>
                </button>
                <button className="secondary-button compact-button" onClick={() => navigate("settings")} type="button">
                  <Settings size={15} />
                  <span>Cài đặt</span>
                </button>
              </div>
            </>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="status-popover-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function titleFor(panel: StatusPanel) {
  if (panel === "camera") {
    return "Camera USB";
  }
  if (panel === "model") {
    return "AI model";
  }
  return "Local agent";
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(value);
}

function formatDiag(value: unknown) {
  return value == null ? "" : String(value);
}

function formatDiagNumber(value: unknown) {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? formatNumber(numeric) : "-";
}

function formatPercent(value: unknown) {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? `${formatNumber(numeric * 100)}%` : "-";
}

function shortTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

function formatStatusMessage(value?: string) {
  if (!value) {
    return "";
  }
  return value
    .replace("Camera idle", "Camera đang chờ")
    .replace("Camera stopped", "Camera đã dừng")
    .replace("UART OFF", "UART đang tắt")
    .replace("khong gui xuong phan cung", "không gửi xuống phần cứng")
    .replace("configured port not visible", "cổng đã cấu hình chưa hiển thị");
}
