"use client";

import { AlertTriangle, Save, Wifi } from "lucide-react";

import type { AppConfig, AudioVoicePackStatusResponse } from "@/lib/agent";
import { NumberField } from "@/components/primitives/number-field";

type SettingsCapturePanelProps = {
  busy: boolean;
  config: AppConfig;
  voicePackStatus: AudioVoicePackStatusResponse | null;
  onChange: (patch: (cfg: AppConfig) => AppConfig) => void;
  onSave: (cfg: AppConfig) => void;
};

export function SettingsCapturePanel({ busy, config, voicePackStatus, onChange, onSave }: SettingsCapturePanelProps) {
  return (
    <div className="panel">
      <span className="eyebrow">Capture</span>
      <div className={config.capture.mode === "auto_low_conf" ? "capture-warning" : "capture-note"}>
        <AlertTriangle size={16} />
        <span>
          {config.capture.mode === "auto_low_conf"
            ? "Auto low confidence đang tự ghi ảnh vào dataset. Chỉ bật khi bạn đang thu data có kiểm soát."
            : "Capture đang an toàn. Ảnh training chỉ vào CSDL khi bạn thêm thủ công hoặc chủ động bật thu data."}
        </span>
      </div>
      <div className="form-grid two-col">
        <label>
          Chế độ
          <select
            value={config.capture.mode}
            onChange={(event) =>
              onChange((cfg) => ({
                ...cfg,
                capture: {
                  ...cfg.capture,
                  mode: event.target.value as "off" | "manual" | "auto_low_conf"
                }
              }))
            }
          >
            <option value="off">Tắt</option>
            <option value="manual">Manual</option>
            <option value="auto_low_conf">Auto low confidence</option>
          </select>
        </label>
        <NumberField
          label="Ngưỡng low confidence"
          max={1}
          min={0}
          step={0.01}
          value={config.capture.low_conf_threshold}
          onValue={(value) =>
            onChange((cfg) => ({
              ...cfg,
              capture: { ...cfg.capture, low_conf_threshold: value }
            }))
          }
        />
      </div>
      <div className="policy-strip">
        <Wifi size={18} />
        <div>
          <strong>Loa phân loại</strong>
          <span>Đọc đúng 3 nhóm: Hữu cơ, Tái chế, Vô cơ</span>
        </div>
      </div>
      <div className="form-grid two-col">
        <label>
          Phát bằng
          <select
            value={config.speaker.output_mode ?? (config.speaker.enabled ? "computer_speaker" : "hardware")}
            onChange={(event) => {
              const outputMode = event.target.value as "hardware" | "computer_speaker";
              onChange((cfg) => ({
                ...cfg,
                speaker: {
                  ...cfg.speaker,
                  output_mode: outputMode,
                  enabled: outputMode === "computer_speaker"
                }
              }));
            }}
          >
            <option value="hardware">Phần cứng</option>
            <option value="computer_speaker">Loa máy tính</option>
          </select>
        </label>
        <label>
          Giọng loa máy tính
          <select
            value={config.speaker.voice_gender ?? "female"}
            onChange={(event) => {
              const voiceGender = event.target.value as "female" | "male";
              onChange((cfg) => ({
                ...cfg,
                speaker: {
                  ...cfg.speaker,
                  voice_gender: voiceGender
                }
              }));
            }}
          >
            <option value="female">Giọng nữ</option>
            <option value="male">Giọng nam</option>
          </select>
        </label>
        <NumberField
          label="Cooldown loa (giây)"
          max={60}
          min={0}
          step={0.5}
          value={config.speaker.cooldown_seconds}
          onValue={(value) =>
            onChange((cfg) => ({
              ...cfg,
              speaker: { ...cfg.speaker, cooldown_seconds: value }
            }))
          }
        />
      </div>
      {voicePackStatus ? (
        <div className={voicePackStatus.missing_events.length ? "capture-warning" : "capture-note"}>
          <Wifi size={16} />
          <span>
            Voice pack {voicePackStatus.gender === "male" ? "giọng nam" : "giọng nữ"}:{" "}
            {voicePackStatus.available_count}/{voicePackStatus.total_count} event.
            {voicePackStatus.missing_events.length
              ? ` Thiếu: ${voicePackStatus.missing_events.join(", ")}.`
              : " Đủ file cho startup, phân loại, cảnh báo đầy thùng và cảnh báo nhiều vật."}
          </span>
        </div>
      ) : null}
      <button className="primary-button" disabled={busy} onClick={() => onSave(config)} type="button">
        <Save size={17} />
        <span>Lưu cài đặt</span>
      </button>
    </div>
  );
}
