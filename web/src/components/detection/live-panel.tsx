"use client";

import { Camera, Play, RefreshCcw, ShieldCheck, Square } from "lucide-react";

import type { Detection, RuntimeStatus, TrainingStatus } from "@/lib/agent";
import { DetectionOverlay } from "@/components/primitives/detection-overlay";

// --- Local helpers ---

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

function formatScore(value: number) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 3,
    minimumFractionDigits: 3
  }).format(value);
}

function numericDiagnostic(value: unknown) {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function cameraHealthDetail(status: RuntimeStatus | null) {
  if (!status) {
    return "";
  }
  const diagnostics = status.camera_diagnostics ?? {};
  const reason = diagnostics.reason ? String(diagnostics.reason) : status.camera.message;
  const mean = numericDiagnostic(diagnostics.mean_brightness);
  const nonBlack = numericDiagnostic(diagnostics.non_black_ratio);
  const metrics = [
    mean == null ? "" : `mean ${Math.round(mean)}`,
    nonBlack == null ? "" : `non-black ${Math.round(nonBlack * 100)}%`
  ].filter(Boolean);
  return [reason, ...metrics].filter(Boolean).join(" | ");
}

// --- MetricCard ---

function MetricCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="metric-card">
      <span className="eyebrow">{label}</span>
      <strong>{value}</strong>
      <small>{detail || "-"}</small>
    </div>
  );
}

// --- Props ---

export type LivePanelProps = {
  busy: boolean;
  detections: Detection[];
  status: RuntimeStatus | null;
  stream: string;
  training: TrainingStatus | null;
  onRefreshDevices: () => void;
  onStart: () => void;
  onStop: () => void;
};

// --- Component ---

export function LivePanel({
  busy,
  detections,
  status,
  stream,
  training,
  onRefreshDevices,
  onStart,
  onStop
}: LivePanelProps) {
  const trainEpoch =
    training?.completed_epoch && training?.target_epoch
      ? `${training.completed_epoch}/${training.target_epoch}`
      : training?.segment_epoch && training?.segment_epochs
        ? `${training.segment_epoch}/${training.segment_epochs}`
        : training?.running
          ? "Đang chạy"
          : "OFF";
  const trainDetail = training?.map5095 != null
    ? `mAP50-95 ${formatScore(training.map5095)}`
    : training?.message || "Chưa có metric";
  return (
    <section className="content-grid live-grid">
      <div className="stat-row">
        <MetricCard
          label="Camera"
          value={status?.camera.running ? "ON" : "OFF"}
          detail={cameraHealthDetail(status)}
        />
        <MetricCard label="FPS" value={formatNumber(status?.fps ?? 0)} detail="Stream realtime" />
        <MetricCard label="Độ trễ" value={`${formatNumber(status?.latency_ms ?? 0)} ms`} detail="Nhận diện" />
        <MetricCard label="UART" value={status?.uart.connected ? "ON" : "OFF"} detail={status?.uart.message} />
        <MetricCard label="Training" value={trainEpoch} detail={trainDetail} />
        <MetricCard
          label="3-Bin"
          value={status?.three_bin_classifier.running ? "ON" : "OFF"}
          detail={status?.three_bin_classifier.message || "Kaggle fallback"}
        />
      </div>

      <div className="camera-panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Camera trực tiếp</span>
            <strong>{status?.current_source || "USB camera chưa chọn"}</strong>
          </div>
          <div className="button-row">
            <button className="secondary-button" disabled={busy} onClick={onRefreshDevices} type="button">
              <RefreshCcw size={17} />
              <span>Làm mới USB</span>
            </button>
            <button className="primary-button" disabled={busy} onClick={onStart} type="button">
              <Play size={17} />
              <span>Quét USB</span>
            </button>
            <button className="danger-button" disabled={busy} onClick={onStop} type="button">
              <Square size={16} />
              <span>Dừng</span>
            </button>
          </div>
        </div>
        <div className="camera-stage">
          {status?.camera.running && stream ? (
            <>
              <img className="camera-stream" src={stream} alt="USB camera stream" />
              <div className="scan-line" />
              <div className="vision-overlay">
                <ShieldCheck size={16} />
                <span>AI vision online</span>
              </div>
              <DetectionOverlay detections={detections} />
            </>
          ) : status?.camera.running ? (
            <div className="black-frame">
              <Camera size={42} />
              <span>Đang cấp quyền stream camera...</span>
            </div>
          ) : (
            <div className="black-frame">
              <Camera size={42} />
              <span>Không có camera USB ngoài hoặc camera đang tắt</span>
            </div>
          )}
        </div>
      </div>

      <div className="side-panel">
        <span className="eyebrow">AI Detection</span>
        <div className="detection-list">
          {detections.length ? (
            detections.slice(0, 8).map((item, index) => (
              <div className="detection-card" key={`${item.timestamp}-${index}`}>
                <div>
                  <strong>{item.cls_name}</strong>
                  <small>
                    {item.route_label || "Chưa mapping"} {item.bin_index ? `- thùng ${item.bin_index}` : ""}
                  </small>
                  <small>
                    {item.serial_payload ? `Serial: ${item.serial_payload}` : "UART payload: -"}
                    {item.ack ? ` - ${item.ack}` : ""}
                  </small>
                  <small>Nguồn: {item.source || "YOLO"}</small>
                </div>
                <span>{Math.round(item.confidence * 100)}%</span>
              </div>
            ))
          ) : (
            <div className="empty-state">Chưa có detection mới.</div>
          )}
        </div>
      </div>
    </section>
  );
}
