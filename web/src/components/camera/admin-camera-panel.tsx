"use client";

import { Camera, Play, RefreshCcw, Save, Square, Zap } from "lucide-react";

import { DeviceList } from "@/components/primitives/device-list";
import { NumberField } from "@/components/primitives/number-field";
import type { AppConfig, RuntimeStatus } from "@/lib/agent";

type AdminCameraPanelProps = {
  busy: boolean;
  config: AppConfig | null;
  status: RuntimeStatus | null;
  stream: string;
  onChange: (patch: (cfg: AppConfig) => AppConfig) => void;
  onRefreshDevices: () => void;
  onSave: (cfg: AppConfig) => void;
  onStart: () => void;
  onStop: () => void;
};

export function AdminCameraPanel({
  busy,
  config,
  status,
  stream,
  onChange,
  onRefreshDevices,
  onSave,
  onStart,
  onStop
}: AdminCameraPanelProps) {
  if (!config) {
    return <div className="empty-state">Đang tải cấu hình camera...</div>;
  }

  const selectedSource = config.camera.source || status?.current_source || "";
  const usbCameras = status?.usb_cameras ?? [];

  return (
    <section className="content-grid camera-management-grid">
      <div className="camera-panel camera-management-preview">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Camera USB</span>
            <strong>{status?.camera.running ? "Đang chạy" : "Đang tắt"}</strong>
          </div>
          <div className="button-row">
            <button className="secondary-button" disabled={busy} onClick={onRefreshDevices} type="button">
              <RefreshCcw size={17} />
              <span>Quét USB</span>
            </button>
            {status?.camera.running ? (
              <button className="danger-button" disabled={busy} onClick={onStop} type="button">
                <Square size={16} />
                <span>Dừng camera</span>
              </button>
            ) : (
              <button className="primary-button" disabled={busy} onClick={onStart} type="button">
                <Play size={17} />
                <span>Bật camera</span>
              </button>
            )}
          </div>
        </div>
        <div className="camera-stage">
          {status?.camera.running && stream ? (
            <img className="camera-stream" src={stream} alt="USB camera stream" />
          ) : (
            <div className="black-frame">
              <Camera size={42} />
              <span>{status?.camera.message || "Camera USB ngoài chưa chạy"}</span>
            </div>
          )}
        </div>
      </div>

      <aside className="side-panel camera-diagnostics-panel">
        <span className="eyebrow">Chẩn đoán nhanh</span>
        <div className="diagnostic-list">
          <DiagnosticRow label="Nguồn hiện tại" value={status?.current_source || selectedSource || "Chưa chọn"} />
          <DiagnosticRow label="Thiết bị USB" value={String(usbCameras.length)} />
          <DiagnosticRow label="FPS" value={formatNumber(status?.fps ?? 0)} />
          <DiagnosticRow label="Độ trễ" value={`${formatNumber(status?.latency_ms ?? 0)} ms`} />
          <DiagnosticRow label="Backend" value={formatDiagnostic(status?.camera_diagnostics?.backend)} />
          <DiagnosticRow label="Mean brightness" value={formatDiagnostic(status?.camera_diagnostics?.mean_brightness)} />
          <DiagnosticRow label="Non-black" value={formatPercent(status?.camera_diagnostics?.non_black_ratio)} />
        </div>
      </aside>

      <div className="panel camera-config-panel">
        <div className="panel-toolbar no-pad">
          <div>
            <span className="eyebrow">Cấu hình giống Desktop</span>
            <strong>Nguồn, độ phân giải, xoay/lật và ROI</strong>
          </div>
          <button
            className="primary-button"
            disabled={busy}
            onClick={() => onSave({ ...config, camera: { ...config.camera, source: selectedSource } })}
            type="button"
          >
            <Save size={17} />
            <span>Lưu cấu hình</span>
          </button>
        </div>

        <div className="policy-strip">
          <Zap size={18} />
          <div>
            <strong>USB only</strong>
            <span>Không fallback webcam laptop; chọn camera ngoài rồi lưu trước khi bật.</span>
          </div>
        </div>

        <div className="form-grid two-col">
          <label>
            Nguồn camera
            <select
              value={selectedSource}
              onChange={(event) =>
                onChange((cfg) => ({ ...cfg, camera: { ...cfg.camera, source: event.target.value } }))
              }
            >
              <option value="">Chưa chọn camera USB</option>
              {usbCameras.map((row, index) => {
                const source = String(row.source ?? row.index ?? row.device ?? "");
                const label = String((row.label ?? row.name ?? row.device ?? source) || `Camera ${index + 1}`);
                return (
                  <option key={`${source}-${index}`} value={source}>
                    {label}
                  </option>
                );
              })}
              {selectedSource && !usbCameras.some((row) => String(row.source ?? row.index ?? row.device ?? "") === selectedSource) ? (
                <option value={selectedSource}>{selectedSource}</option>
              ) : null}
            </select>
          </label>
          <NumberField
            label="Chiều rộng"
            min={160}
            max={7680}
            step={10}
            value={config.camera.width}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, camera: { ...cfg.camera, width: Math.round(value) } }))
            }
          />
          <NumberField
            label="Chiều cao"
            min={120}
            max={4320}
            step={10}
            value={config.camera.height}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, camera: { ...cfg.camera, height: Math.round(value) } }))
            }
          />
          <label>
            Xoay camera
            <select
              value={config.camera.rotation}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  camera: { ...cfg.camera, rotation: Number(event.target.value) as 0 | 90 | 180 | 270 }
                }))
              }
            >
              <option value={0}>0° - mốc ban đầu</option>
              <option value={90}>90° phải</option>
              <option value={180}>180°</option>
              <option value={270}>90° trái</option>
            </select>
          </label>
          <label className="check-field">
            <input
              checked={config.camera.mirror}
              onChange={(event) =>
                onChange((cfg) => ({ ...cfg, camera: { ...cfg.camera, mirror: event.target.checked } }))
              }
              type="checkbox"
            />
            Lật ngang
          </label>
        </div>

        <div className="divider" />
        <div className="form-grid two-col">
          <label className="check-field">
            <input
              checked={config.roi.enabled}
              onChange={(event) =>
                onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, enabled: event.target.checked } }))
              }
              type="checkbox"
            />
            Bật ROI vùng khay
          </label>
          <label className="check-field">
            <input
              checked={config.dispatch_guard.require_roi_for_dispatch}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  dispatch_guard: { ...cfg.dispatch_guard, require_roi_for_dispatch: event.target.checked }
                }))
              }
              type="checkbox"
            />
            Bắt buộc ROI để gửi lệnh
          </label>
          <NumberField
            label="ROI X"
            min={0}
            max={7680}
            step={1}
            value={config.roi.x}
            onValue={(value) => onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, x: Math.round(value) } }))}
          />
          <NumberField
            label="ROI Y"
            min={0}
            max={4320}
            step={1}
            value={config.roi.y}
            onValue={(value) => onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, y: Math.round(value) } }))}
          />
          <NumberField
            label="ROI width"
            min={0}
            max={7680}
            step={1}
            value={config.roi.width}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, width: Math.round(value) } }))
            }
          />
          <NumberField
            label="ROI height"
            min={0}
            max={4320}
            step={1}
            value={config.roi.height}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, height: Math.round(value) } }))
            }
          />
        </div>
      </div>

      <div className="panel">
        <div className="panel-toolbar no-pad">
          <div>
            <span className="eyebrow">Thiết bị tìm thấy</span>
            <strong>Camera USB ngoài</strong>
          </div>
        </div>
        <DeviceList rows={usbCameras} empty="Không thấy camera USB ngoài. Cắm camera rồi bấm Quét USB." />
      </div>
    </section>
  );
}

function DiagnosticRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="diagnostic-row">
      <span>{label}</span>
      <strong>{value || "-"}</strong>
    </div>
  );
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

function formatDiagnostic(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(Math.round(value * 1000) / 1000) : "-";
  }
  return String(value);
}

function formatPercent(value: unknown) {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? `${Math.round(numeric * 100)}%` : "-";
}
