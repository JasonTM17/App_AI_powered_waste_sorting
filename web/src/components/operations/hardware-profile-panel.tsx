"use client";

import { AlertTriangle, CheckCircle2, MousePointer2, RefreshCcw, Zap } from "lucide-react";

import type { HardwareDiagnostics, HardwareProfile, HardwareTestResponse } from "@/lib/agent";
import { HardwareDiagnosticsPanel } from "@/components/operations/hardware-diagnostics-panel";
import { StatusPill } from "@/components/primitives/status-pill";

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

type HardwareProfilePanelProps = {
  busy: boolean;
  diagnostics: HardwareDiagnostics | null;
  profile: HardwareProfile | null;
  test: HardwareTestResponse | null;
  onAudioTrackTest: (track: number) => void;
  onHomeAngleTest: (d6: number, d7: number, label: string) => void;
  onMp3Test: (command: Mp3TestCommand, value?: number) => void;
  onReconnect: () => void;
  onServoAngleTest: (d6: number, d7: number, label: string) => void;
  onSortAngleTest: (command: "O" | "R" | "I", d6: number, d7: number, label: string) => void;
  onTest: (command: "O" | "R" | "I") => void;
};

export function HardwareProfilePanel({
  busy,
  diagnostics,
  profile,
  test,
  onAudioTrackTest,
  onHomeAngleTest,
  onMp3Test,
  onReconnect,
  onServoAngleTest,
  onSortAngleTest,
  onTest
}: HardwareProfilePanelProps) {
  if (!profile) {
    return <div className="empty-state">Đang tải mapping phần cứng...</div>;
  }
  const waitDegrees = profile.servo.wait_degrees as Record<string, unknown> | undefined;
  const calibration = profile.calibration ?? {};
  const readAngleCandidate = (item: unknown) => {
    const row = item as Record<string, unknown>;
    const d6 = Number(row.D6 ?? row.d6);
    const d7 = Number(row.D7 ?? row.d7);
    if (!Number.isFinite(d6) || !Number.isFinite(d7)) {
      return null;
    }
    const command = String(row.command || "I").toUpperCase();
    return {
      label: String(row.label || `D6=${d6}, D7=${d7}`),
      command: ["O", "R", "I"].includes(command) ? (command as "O" | "R" | "I") : "I",
      d6,
      d7
    };
  };
  const homeCandidates = Array.isArray(calibration.home_candidates)
    ? calibration.home_candidates.map(readAngleCandidate).filter((item) => item !== null)
    : [
        { label: "Home hiện tại", command: "I" as const, d6: Number(waitDegrees?.D6 ?? 90), d7: Number(waitDegrees?.D7 ?? 85) },
        { label: "Home D7 -2", command: "I" as const, d6: 90, d7: 83 },
        { label: "Home D7 +2", command: "I" as const, d6: 90, d7: 87 },
        { label: "Home D6 -2", command: "I" as const, d6: 88, d7: 85 },
        { label: "Home D6 +2", command: "I" as const, d6: 92, d7: 85 }
      ];
  const inorganicCandidates = Array.isArray(calibration.inorganic_replay_candidates)
    ? calibration.inorganic_replay_candidates.map(readAngleCandidate).filter((item) => item !== null)
    : [
        { label: "Vô cơ hiện tại", command: "R" as const, d6: 90, d7: 0 },
        { label: "Vô cơ trước đó", command: "R" as const, d6: 145, d7: 180 },
        { label: "Vô cơ max max", command: "R" as const, d6: 180, d7: 180 },
        { label: "Vô cơ D6 min", command: "R" as const, d6: 0, d7: 180 },
        { label: "Vô cơ D7 min", command: "R" as const, d6: 180, d7: 0 },
        { label: "Vô cơ cả hai min", command: "R" as const, d6: 0, d7: 0 },
        { label: "Vô cơ D6 45", command: "R" as const, d6: 45, d7: 180 },
        { label: "Vô cơ D7 45", command: "R" as const, d6: 180, d7: 45 }
      ];
  const inorganicRoute = profile.routes.find((route) => String(route.command).toUpperCase() === "R");
  const calibrationPositions = [
    {
      label: "Wait",
      d6: Number(waitDegrees?.D6 ?? 90),
      d7: Number(waitDegrees?.D7 ?? 85)
    },
    ...profile.routes.flatMap((route) => {
      const positions = route.servo_positions as Record<string, unknown> | undefined;
      const d6 = Number(positions?.D6);
      const d7 = Number(positions?.D7);
      if (!Number.isFinite(d6) || !Number.isFinite(d7)) {
        return [];
      }
      return [
        {
          label: String(route.label || route.command || "Route"),
          d6,
          d7
        }
      ];
    })
  ];
  const audioTracks = [
    { label: "Startup", track: Number(profile.gd5800.startup_track ?? 1) },
    ...profile.routes.map((route) => ({
      label: `${String(route.label || route.command || "Route")} sort`,
      track: Number(route.gd5800_track)
    })),
    ...(profile.proximity_sensors ?? []).map((sensor) => ({
      label: `${String(sensor.label || sensor.command || "Sensor")} sensor`,
      track: Number(sensor.gd5800_track)
    })),
    { label: "Multi-object warning", track: Number(profile.gd5800.multi_object_warning_track ?? 8) }
  ].filter((item) => Number.isFinite(item.track) && item.track > 0);

  const mp3Tests = [
    { label: "Mode Primary D5/D4", command: "MODE_PRIMARY" as const },
    { label: "Mode Reverse D4/D5", command: "MODE_REVERSE" as const },
    { label: "Mode?", command: "MODE_QUERY" as const },
    { label: "Select TF", command: "TF" as const },
    { label: "TF Online?", command: "ONLINE" as const },
    { label: "Status?", command: "STATUS" as const },
    { label: "Volume 30", command: "VOL" as const, value: 30 },
    { label: "Play 1 index", command: "PLAY" as const, value: 1 },
    { label: "Play 1 + vol", command: "PLAYVOL" as const, value: 1 },
    { label: "Next", command: "NEXT" as const },
    { label: "Reset MP3", command: "RESET" as const }
  ];
  return (
    <div className="panel full-span">
      <div className="panel-toolbar no-pad">
        <div>
          <span className="eyebrow">Mapping phần cứng</span>
          <strong>{profile.profile_id || profile.current_port || "UART OFF"}</strong>
          <p className="muted">{profile.uart_message || "Chưa có trạng thái UART."}</p>
        </div>
        <button
          className="secondary-button"
          disabled={busy}
          onClick={onReconnect}
          type="button"
        >
          <RefreshCcw size={17} />
          <span>Reconnect UART</span>
        </button>
      </div>
      <div className={diagnostics?.warning ? "capture-warning" : "success"}>
        {diagnostics?.warning ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
        <span>
          {diagnostics?.warning ||
            `UART OK; profile ${diagnostics?.firmware_profile || profile.profile_id || "unknown"}`}
        </span>
      </div>
      <div className="hardware-grid">
        {profile.routes.map((route) => {
          const command = String(route.command || "") as "O" | "R" | "I";
          const positions = route.servo_positions
            ? Object.entries(route.servo_positions as Record<string, unknown>)
                .map(([pin, angle]) => `${pin}=${String(angle)}`)
                .join(", ")
            : "";
          return (
            <div className="hardware-route" key={command}>
              <span className={`bin-pill bin-pill-${command.toLowerCase()}`}>{String(route.label || command)}</span>
              <strong>
                {command}
                {" -> "}
                {String(route.serial_payload || "")}
                {"\\n"}
              </strong>
              <small>
                Thùng {String(route.bin_index)} - servo {String(route.servo_pin)}
                {positions ? ` (${positions})` : ""} - GD5800 sort track{" "}
                {String(route.gd5800_track)}
              </small>
              <button
                className="secondary-button compact-button"
                disabled={busy || !profile.current_port}
                onClick={() => onTest(command)}
                type="button"
              >
                <MousePointer2 size={15} />
                <span>Test</span>
              </button>
            </div>
          );
        })}
      </div>
      <div className="hardware-meta">
        <div className="policy-strip">
          <MousePointer2 size={18} />
          <div>
            <strong>Hiệu chuẩn home/upright</strong>
            <span>Replay offset nhỏ và chọn góc khi khay đứng thẳng, không bị nghiêng.</span>
          </div>
        </div>
        <div className="hardware-grid">
          {homeCandidates.map((item) => (
            <button
              className="secondary-button compact-button"
              disabled={busy || !profile.current_port}
              key={`home-${item.label}-${item.d6}-${item.d7}`}
              onClick={() => onHomeAngleTest(item.d6, item.d7, item.label)}
              type="button"
            >
              <MousePointer2 size={15} />
              <span>
                HOME {item.label}: D6={item.d6}, D7={item.d7}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="hardware-meta">
        <div className="policy-strip">
          <MousePointer2 size={18} />
          <div>
            <strong>Replay hướng vô cơ</strong>
            <span>
              Mỗi nút gửi SORTTEST R, phát track {String(inorganicRoute?.gd5800_track ?? 4)}, đổ theo góc thử, rồi trở về home hiện tại.
            </span>
          </div>
        </div>
        <div className="hardware-grid">
          {inorganicCandidates.map((item) => (
            <button
              className="secondary-button compact-button"
              disabled={busy || !profile.current_port}
              key={`sort-${item.label}-${item.d6}-${item.d7}`}
              onClick={() => onSortAngleTest(item.command, item.d6, item.d7, item.label)}
              type="button"
            >
              <MousePointer2 size={15} />
              <span>
                SORTTEST {item.label}: D6={item.d6}, D7={item.d7}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="hardware-meta">
        <div className="policy-strip">
          <MousePointer2 size={18} />
          <div>
            <strong>Hiệu chuẩn servo thô D6/D7</strong>
            <span>Chỉ dùng cặp góc thô để kiểm tra; thao tác này không phát audio phân loại.</span>
          </div>
        </div>
        <div className="hardware-grid">
          {calibrationPositions.map((item) => (
            <button
              className="secondary-button compact-button"
              disabled={busy || !profile.current_port}
              key={`${item.label}-${item.d6}-${item.d7}`}
              onClick={() => onServoAngleTest(item.d6, item.d7, item.label)}
              type="button"
            >
              <MousePointer2 size={15} />
              <span>
                {item.label}: D6={item.d6}, D7={item.d7}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="hardware-meta">
        <div className="policy-strip">
          <Zap size={18} />
          <div>
            <strong>GD5800</strong>
            <span>
              Startup track {String(profile.gd5800.startup_track)} - TX {String(profile.gd5800.tx_pin)} - RX{" "}
              {String(profile.gd5800.rx_pin)} - {String(profile.audio_protocol || profile.gd5800.audio_protocol || "audio")} - route audio 2/3/4, sensor audio 5/6/7
            </span>
          </div>
        </div>
        <div className="device-list">
          {(profile.proximity_sensors ?? []).map((sensor) => (
            <div className="device-row" key={String(sensor.pin)}>
              <strong>Cảm biến âm thanh {String(sensor.label || sensor.command)}</strong>
              <span>
                pin {String(sensor.pin)}, active {String(sensor.active_level)}, track{" "}
                {String(sensor.gd5800_track)}, action {String(sensor.action || "audio_only")}
              </span>
              <StatusPill ok={!sensor.controls_servo} text={sensor.controls_servo ? "servo" : "audio only"} />
            </div>
          ))}
        </div>
        <div className="hardware-grid">
          {mp3Tests.map((item) => (
            <button
              className="secondary-button compact-button"
              disabled={busy || !profile.current_port}
              key={`${item.command}-${item.value ?? ""}`}
              onClick={() => onMp3Test(item.command, item.value)}
              type="button"
            >
              <Zap size={15} />
              <span>
                MP3 {item.label}
              </span>
            </button>
          ))}
        </div>
        <div className="hardware-grid">
          {audioTracks.map((item) => (
            <button
              className="secondary-button compact-button"
              disabled={busy || !profile.current_port}
              key={`${item.label}-${item.track}`}
              onClick={() => onAudioTrackTest(item.track)}
              type="button"
            >
              <Zap size={15} />
              <span>
                Audio {item.track}: {item.label}
              </span>
            </button>
          ))}
        </div>
      </div>
      {diagnostics || test ? (
        <HardwareDiagnosticsPanel diagnostics={diagnostics} test={test} />
      ) : null}
    </div>
  );
}
