import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { HardwareProfilePanel } from "@/components/operations/hardware-profile-panel";
import type { HardwareProfile } from "@/lib/agent";
import { renderWithProviders } from "../helpers/render-with-providers";

const profile: HardwareProfile = {
  profile_id: "LEGACY_2_SERVO_OPENSMART",
  profile_name: "Two servo profile",
  audio_protocol: "open_smart_serial_mp3_a",
  baud: 9600,
  protocol: "plain_group",
  current_port: "COM8",
  uart_message: "UART OK",
  servo: {
    wait_degrees: { D6: 90, D7: 85 }
  },
  calibration: {},
  gd5800: {
    startup_track: 1,
    multi_object_warning_track: 8
  },
  routes: [
    {
      command: "O",
      label: "Huu co",
      serial_payload: "huuco",
      bin_index: 1,
      servo_pin: "D6/D7",
      servo_positions: { D6: 90, D7: 180 },
      gd5800_track: 2
    },
    {
      command: "R",
      label: "Vo co",
      serial_payload: "voco",
      bin_index: 2,
      servo_pin: "D6/D7",
      servo_positions: { D6: 90, D7: 0 },
      gd5800_track: 4
    },
    {
      command: "I",
      label: "Tai che",
      serial_payload: "taiche",
      bin_index: 3,
      servo_pin: "D6/D7",
      servo_positions: { D6: 145, D7: 180 },
      gd5800_track: 3
    }
  ],
  bin_sensors: [],
  proximity_sensors: [
    { command: "O", label: "Huu co", pin: "D10", active_level: 0, gd5800_track: 5, action: "audio_only", controls_servo: false },
    { command: "I", label: "Tai che", pin: "D11", active_level: 0, gd5800_track: 6, action: "audio_only", controls_servo: false },
    { command: "R", label: "Vo co", pin: "D12", active_level: 0, gd5800_track: 7, action: "audio_only", controls_servo: false }
  ]
};

describe("HardwareProfilePanel", () => {
  it("uses route audio tracks from the hardware profile instead of fixed button order", async () => {
    const onAudioTrackTest = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <HardwareProfilePanel
        busy={false}
        diagnostics={null}
        profile={profile}
        test={null}
        onAudioTrackTest={onAudioTrackTest}
        onHomeAngleTest={vi.fn()}
        onMp3Test={vi.fn()}
        onReconnect={vi.fn()}
        onServoAngleTest={vi.fn()}
        onSortAngleTest={vi.fn()}
        onTest={vi.fn()}
      />
    );

    await user.click(screen.getByRole("button", { name: /Audio 4: Vo co sort/i }));
    await user.click(screen.getByRole("button", { name: /Audio 3: Tai che sort/i }));

    expect(onAudioTrackTest).toHaveBeenNthCalledWith(1, 4);
    expect(onAudioTrackTest).toHaveBeenNthCalledWith(2, 3);
  });
});
