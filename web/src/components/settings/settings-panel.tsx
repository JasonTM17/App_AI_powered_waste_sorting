"use client";

import type {
  ActuationTestMode,
  AppConfig,
  AudioVoicePackStatusResponse,
  HardwareDiagnostics,
  HardwareProfile,
  HardwareTestResponse,
  RuntimeStatus
} from "@/lib/agent";
import { ActuationTestModePanel } from "@/components/operations/actuation-test-mode-panel";
import { HardwareProfilePanel } from "@/components/operations/hardware-profile-panel";
import { SettingsCapturePanel } from "@/components/settings/settings-capture-panel";
import { SettingsIoPanel } from "@/components/settings/settings-io-panel";
import { SettingsModelPanel } from "@/components/settings/settings-model-panel";
import { AudioSettingsPanel } from "@/components/settings/audio-settings-panel";

type Mp3TestCommand =
  | "TF"
  | "VOL"
  | "PLAY"
  | "PLAYVOL"
  | "NEXT"
  | "ONLINE"
  | "STATUS"
  | "RESET"
  | "MODE_PRIMARY"
  | "MODE_REVERSE"
  | "MODE_QUERY";

type SettingsPanelProps = {
  /** Local desktop may operate physical hardware; cloud Admin must not expose actuation. */
  allowHardwareActuation: boolean;
  mode: "settings" | "model" | "audio";
  actuationMode: ActuationTestMode | null;
  busy: boolean;
  config: AppConfig | null;
  hardwareDiagnostics: HardwareDiagnostics | null;
  hardwareProfile: HardwareProfile | null;
  hardwareTest: HardwareTestResponse | null;
  status: RuntimeStatus | null;
  voicePackStatus: AudioVoicePackStatusResponse | null;
  onChange: (patch: (cfg: AppConfig) => AppConfig) => void;
  onRefreshDevices: () => void;
  onReconnectHardware: () => void;
  onSave: (cfg: AppConfig) => void;
  onToggleActuationMode: (enabled: boolean) => void;
  onTestAudioTrack: (track: number) => void;
  onTestHomeAngles: (d6: number, d7: number, label: string) => void;
  onTestMp3: (command: Mp3TestCommand, value?: number) => void;
  onTestServoAngles: (d6: number, d7: number, label: string) => void;
  onTestSortAngles: (command: "O" | "R" | "I", d6: number, d7: number, label: string) => void;
  onTestHardware: (command: "O" | "R" | "I") => void;
};

export function SettingsPanel({
  allowHardwareActuation,
  mode,
  actuationMode,
  busy,
  config,
  hardwareDiagnostics,
  hardwareProfile,
  hardwareTest,
  status,
  voicePackStatus,
  onChange,
  onRefreshDevices,
  onReconnectHardware,
  onSave,
  onToggleActuationMode,
  onTestAudioTrack,
  onTestHomeAngles,
  onTestMp3,
  onTestServoAngles,
  onTestSortAngles,
  onTestHardware
}: SettingsPanelProps) {
  if (!config) {
    return <div className="empty-state">Đang tải cài đặt...</div>;
  }
  if (mode === "model") return <section className="content-grid settings-grid"><SettingsModelPanel config={config} status={status} onChange={onChange} /><button className="primary-button" disabled={busy} onClick={() => onSave(config)} type="button">Lưu cấu hình model</button></section>;
  if (mode === "audio") return <section className="content-grid settings-grid"><AudioSettingsPanel config={config} profile={hardwareProfile} voicePack={voicePackStatus} busy={busy} onChange={onChange} onSave={onSave} onTest={onTestAudioTrack}/></section>;
  return (
    <section className="content-grid settings-grid">
      <SettingsIoPanel
        busy={busy}
        config={config}
        status={status}
        onChange={onChange}
        onRefreshDevices={onRefreshDevices}
      />

      {!allowHardwareActuation || !hardwareProfile ? null : <HardwareProfilePanel
        busy={busy}
        diagnostics={hardwareDiagnostics}
        profile={hardwareProfile}
        test={hardwareTest}
        onReconnect={onReconnectHardware}
        onAudioTrackTest={onTestAudioTrack}
        onMp3Test={onTestMp3}
        onHomeAngleTest={onTestHomeAngles}
        onServoAngleTest={onTestServoAngles}
        onSortAngleTest={onTestSortAngles}
        onTest={onTestHardware}
      />}

      {!allowHardwareActuation ? null : <ActuationTestModePanel
        busy={busy}
        mode={actuationMode}
        onToggle={onToggleActuationMode}
      />}

      <SettingsCapturePanel
        busy={busy}
        config={config}
        voicePackStatus={voicePackStatus}
        onChange={onChange}
        onSave={onSave}
      />
    </section>
  );
}
