"use client";

import { AlertTriangle, RefreshCcw, Zap } from "lucide-react";

import type { AppConfig, RuntimeStatus } from "@/lib/agent";
import { DeviceList } from "@/components/primitives/device-list";
import { NumberField } from "@/components/primitives/number-field";

type SettingsIoPanelProps = {
  busy: boolean;
  config: AppConfig;
  status: RuntimeStatus | null;
  onChange: (patch: (cfg: AppConfig) => AppConfig) => void;
  onRefreshDevices: () => void;
};

export function SettingsIoPanel({ busy, config, status, onChange, onRefreshDevices }: SettingsIoPanelProps) {
  const usbPorts = status?.serial_ports.filter((port) => Boolean(port.is_usb)) ?? [];
  return (
    <>
      <div className="panel">
        <div className="panel-toolbar no-pad">
          <div>
            <span className="eyebrow">Camera USB</span>
            <strong>{status?.usb_cameras.length ?? 0} thiết bị ngoài</strong>
          </div>
          <button className="secondary-button" disabled={busy} onClick={onRefreshDevices} type="button">
            <RefreshCcw size={17} />
            <span>Làm mới USB</span>
          </button>
        </div>
        <div className="policy-strip">
          <Zap size={18} />
          <div>
            <strong>USB only</strong>
            <span>Không fallback webcam máy tính</span>
          </div>
        </div>
        <DeviceList rows={status?.usb_cameras ?? []} empty="Không thấy camera USB ngoài." />
        <div className="form-grid two-col">
          <label>
            Xoay camera
            <select
              value={config.camera.rotation}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  camera: {
                    ...cfg.camera,
                    rotation: Number(event.target.value) as 0 | 90 | 180 | 270
                  }
                }))
              }
            >
              <option value={0}>0° - mốc ban đầu</option>
              <option value={90}>90° phải</option>
              <option value={180}>180°</option>
              <option value={270}>90° trái</option>
            </select>
          </label>
        </div>
      </div>

      <div className="panel">
        <span className="eyebrow">UART USB / Arduino</span>
        {!config.uart.port ? (
          <div className="capture-warning">
            <AlertTriangle size={16} />
            <span>UART OFF, không gửi xuống phần cứng. Cắm Arduino USB hoặc chọn đúng cổng rồi lưu.</span>
          </div>
        ) : null}
        <div className="form-grid two-col">
          <label>
            Cổng USB
            <select
              value={config.uart.port}
              onChange={(event) =>
                onChange((cfg) => ({ ...cfg, uart: { ...cfg.uart, port: event.target.value } }))
              }
            >
              <option value="">OFF</option>
              {usbPorts.map((port) => (
                <option key={String(port.device)} value={String(port.device)}>
                  {String(port.device)} - {String(port.name || "USB")}
                </option>
              ))}
            </select>
          </label>
          <NumberField
            label="Baud"
            min={1200}
            step={1200}
            value={config.uart.baud}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, uart: { ...cfg.uart, baud: Math.round(value) } }))
            }
          />
          <NumberField
            label="Timeout ACK ms"
            min={10}
            step={10}
            value={config.uart.ack_timeout_ms}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                uart: { ...cfg.uart, ack_timeout_ms: Math.round(value) }
              }))
            }
          />
          <label>
            Giao thức mạch
            <select
              value={config.uart.protocol}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  uart: {
                    ...cfg.uart,
                    protocol: event.target.value as "plain_group" | "sort_line"
                  }
                }))
              }
            >
              <option value="plain_group">Block: huuco / voco / taiche</option>
              <option value="sort_line">Firmware: SORT:O/R/I</option>
            </select>
          </label>
          <label className="check-field">
            <input
              checked={config.uart.auto_reconnect}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  uart: { ...cfg.uart, auto_reconnect: event.target.checked }
                }))
              }
              type="checkbox"
            />
            Tự kết nối lại
          </label>
        </div>
        <DeviceList rows={status?.serial_ports ?? []} empty="Không thấy cổng USB/Arduino." />
      </div>

      <div className="panel">
        <span className="eyebrow">ROI / chong lap vong</span>
        <div className="capture-warning">
          <AlertTriangle size={16} />
          <span>Camera chi gui UART khi ROI hop le, khay da trong on dinh va het cooldown.</span>
        </div>
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
                  dispatch_guard: {
                    ...cfg.dispatch_guard,
                    require_roi_for_dispatch: event.target.checked
                  }
                }))
              }
              type="checkbox"
            />
            Bắt buộc ROI để đổ
          </label>
          <NumberField
            label="ROI X"
            min={0}
            step={1}
            value={config.roi.x}
            onValue={(value) => onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, x: Math.round(value) } }))}
          />
          <NumberField
            label="ROI Y"
            min={0}
            step={1}
            value={config.roi.y}
            onValue={(value) => onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, y: Math.round(value) } }))}
          />
          <NumberField
            label="ROI width"
            min={0}
            step={1}
            value={config.roi.width}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, width: Math.round(value) } }))
            }
          />
          <NumberField
            label="ROI height"
            min={0}
            step={1}
            value={config.roi.height}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, roi: { ...cfg.roi, height: Math.round(value) } }))
            }
          />
          <NumberField
            label="Cach moi lan do (s)"
            min={0}
            step={0.5}
            value={config.dispatch_guard.min_sort_interval_seconds}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                dispatch_guard: { ...cfg.dispatch_guard, min_sort_interval_seconds: value }
              }))
            }
          />
          <NumberField
            label="Khay trong de re-arm (s)"
            min={0}
            step={0.5}
            value={config.dispatch_guard.empty_rearm_seconds}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                dispatch_guard: { ...cfg.dispatch_guard, empty_rearm_seconds: value }
              }))
            }
          />
          <NumberField
            label="Số class tối đa mỗi lần đổ"
            min={1}
            max={5}
            step={1}
            value={config.dispatch_guard.max_classes_per_dispatch}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                dispatch_guard: { ...cfg.dispatch_guard, max_classes_per_dispatch: Math.round(value) }
              }))
            }
          />
          <NumberField
            label="Cooldown cảnh báo nhiều rác (s)"
            min={0}
            max={120}
            step={1}
            value={config.dispatch_guard.multi_class_warning_cooldown_seconds}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                dispatch_guard: { ...cfg.dispatch_guard, multi_class_warning_cooldown_seconds: value }
              }))
            }
          />
          <NumberField
            label="Track loa cảnh báo"
            min={0}
            max={8}
            step={1}
            value={config.dispatch_guard.multi_class_warning_audio_track}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                dispatch_guard: { ...cfg.dispatch_guard, multi_class_warning_audio_track: Math.round(value) }
              }))
            }
          />
        </div>
      </div>
    </>
  );
}
