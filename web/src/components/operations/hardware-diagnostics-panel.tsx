"use client";

import type { HardwareDiagnostics, HardwareTestResponse } from "@/lib/agent";
import { StatusPill } from "@/components/primitives/status-pill";

function audioSourceLabel(source: unknown) {
  const value = String(source || "").toLowerCase();
  if (value === "sort") return "sort audio";
  if (value === "prox") return "sensor audio";
  if (value === "manual") return "manual test";
  if (value === "startup") return "startup";
  return value || "-";
}

type HardwareDiagnosticsPanelProps = {
  diagnostics: HardwareDiagnostics | null;
  test: HardwareTestResponse | null;
};

export function HardwareDiagnosticsPanel({ diagnostics, test }: HardwareDiagnosticsPanelProps) {
  return (
    <>
      {diagnostics ? (
      <div className="device-list">
        <div className="device-row">
          <strong>Firmware</strong>
          <span>
            {diagnostics.firmware_profile || "-"}; PONG age{" "}
            {diagnostics.last_pong_age_s ?? "-"}s; profile age{" "}
            {diagnostics.firmware_profile_age_s ?? "-"}s
          </span>
          <StatusPill ok={diagnostics.uart_connected} text={diagnostics.uart_connected ? "connected" : "off"} />
        </div>
        <div className="device-row">
          <strong>Last servo ACK / sensor PROX</strong>
          <span>
            servo ACK {String(diagnostics.last_ack.command || "-")} {String(diagnostics.last_ack.kind || "-")};
            sensor PROX{" "}
            {String(diagnostics.last_proximity.command || "-")}
          </span>
          <StatusPill ok={!diagnostics.disconnect_reason} text={diagnostics.disconnect_reason ? "error" : "clear"} />
        </div>
        <div className="device-row">
          <strong>Current home / routes</strong>
          <span>
            home D6={String(diagnostics.current_home.D6 ?? "-")}, D7={String(diagnostics.current_home.D7 ?? "-")};
            vô cơ D6={String((diagnostics.current_vo_co ?? diagnostics.current_inorganic).D6 ?? "-")},
            D7={String((diagnostics.current_vo_co ?? diagnostics.current_inorganic).D7 ?? "-")};
            tái chế D6={String(diagnostics.current_tai_che?.D6 ?? "-")},
            D7={String(diagnostics.current_tai_che?.D7 ?? "-")};
            firmware home {JSON.stringify(diagnostics.last_servo.detail || {})}
          </span>
          <StatusPill ok={diagnostics.current_home.D6 !== undefined} text="calibration" />
        </div>
        <div className="device-row">
          <strong>Last AUDIO</strong>
          <span>
            cmd {String(diagnostics.last_audio.command || "-")}; track{" "}
            {String(diagnostics.last_audio.track || "-")}; source{" "}
            {audioSourceLabel(diagnostics.last_audio.source)}
          </span>
          <StatusPill
            ok={Boolean(diagnostics.last_audio.track)}
            text={diagnostics.last_audio.track ? audioSourceLabel(diagnostics.last_audio.source) : "none"}
          />
        </div>
        <div className="device-row">
          <strong>Last MP3</strong>
          <span>
            {String(diagnostics.last_mp3.event || "-")}: {String(diagnostics.last_mp3.detail || "-")}
          </span>
          <StatusPill ok={Boolean(diagnostics.last_mp3.event)} text={diagnostics.audio_protocol || "open smart"} />
        </div>
        <div className="device-row">
          <strong>Last MP3 TX</strong>
          <span>{String(diagnostics.last_mp3_tx.detail || "-")}</span>
          <StatusPill ok={Boolean(diagnostics.last_mp3_tx.detail)} text="Arduino -> MP3" />
        </div>
        <div className="device-row">
          <strong>Last MP3 RX</strong>
          <span>{String(diagnostics.last_mp3_rx.detail || "-")}</span>
          <StatusPill ok={Boolean(diagnostics.last_mp3_rx.detail)} text="MP3 -> Arduino" />
        </div>
        {diagnostics.disconnect_reason ? (
          <div className="alert">Disconnect: {diagnostics.disconnect_reason}</div>
        ) : null}
      </div>
      ) : null}
      {test ? (
        <div className={test.ok ? "success" : "alert"}>
          {test.message} - payload {test.payload.trim()} - {test.ack_status || "no_ack"} - {test.elapsed_ms} ms
          {["ANGLE", "HOME", "SORTTEST"].includes(String(test.command || "")) ? ` - ${test.label || "angle"} D6=${test.d6}, D7=${test.d7}` : ""}
          {test.route_command ? ` - route ${test.route_command}` : ""}
          {test.track ? ` - track ${test.track}` : ""}
          {test.value ? ` - value ${test.value}` : ""}
          {test.ok &&
          (test.track ||
            ["TF", "VOL", "PLAY", "PLAYVOL", "NEXT", "ONLINE", "STATUS", "RESET", "MODE_PRIMARY", "MODE_REVERSE", "MODE_QUERY"].includes(
              String(test.command || "")
            )) ? (
            <span> - ACK OK chỉ xác nhận Arduino đã gửi lệnh MP3; nếu không nghe hãy kiểm tra microSD, file track, loa, nguồn, TX/RX D4-D5.</span>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
