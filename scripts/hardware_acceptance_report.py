"""Generate a safe hardware acceptance report without actuating hardware."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import load_config
from app.core.hardware_profile import hardware_profile_payload
from app.core.uart_protocol import encode_sort
from app.core.voice_pack import audio_event_path, voice_pack_status
from app.core.waste_categories import (
    CATEGORIES_BY_COMMAND,
    TRAINING_CLASS_ORDER_45,
    category_for_class,
)
from app.utils.camera_enum import list_pnp_cameras
from app.utils.paths import config_path
from app.utils.serial_enum import eligible_usb_serial_ports, list_serial_ports


def build_report() -> dict[str, Any]:
    cfg = load_config(config_path())
    profile = hardware_profile_payload()
    serial_ports = list_serial_ports()
    eligible_ports = eligible_usb_serial_ports(serial_ports)
    cameras = list_pnp_cameras()
    external_cameras = [camera for camera in cameras if camera.get("is_external")]
    voice_gender = cfg.speaker.voice_gender
    route_matrix = []
    routes_by_command = {
        str(route["command"]): route
        for route in profile["routes"]
        if isinstance(route, dict)
    }
    for command, category in CATEGORIES_BY_COMMAND.items():
        route = routes_by_command.get(command, {})
        event_key = f"sort_{command}"
        audio_path = audio_event_path(event_key, voice_gender)
        route_matrix.append(
            {
                "command": command,
                "category": category.name,
                "bin_index": category.bin_index,
                "serial_payload": route.get("serial_payload"),
                "uart_payload": _payload(command, cfg.uart.protocol),
                "laptop_audio_event": event_key,
                "laptop_audio_file": str(audio_path) if audio_path is not None else None,
                "hardware_track": route.get("gd5800_track"),
                "servo_positions": route.get("servo_positions"),
            }
        )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "safe_mode": True,
        "note": "Report only. No camera start, UART write, MP3 playback, or servo command is executed.",
        "config": {
            "camera_source": cfg.camera.source,
            "uart_port": cfg.uart.port,
            "uart_baud": cfg.uart.baud,
            "uart_protocol": cfg.uart.protocol,
            "ack_timeout_ms": cfg.uart.ack_timeout_ms,
            "speaker_output_mode": cfg.speaker.output_mode,
            "speaker_enabled": cfg.speaker.enabled,
            "voice_gender": cfg.speaker.voice_gender,
            "actuation_requires_test_mode": True,
        },
        "hardware_profile": {
            "profile_id": profile["profile_id"],
            "profile_name": profile["profile_name"],
            "audio_protocol": profile["audio_protocol"],
        },
        "devices": {
            "serial_ports": serial_ports,
            "eligible_usb_serial_ports": eligible_ports,
            "pnp_cameras": cameras,
            "external_usb_cameras": external_cameras,
        },
        "voice_pack": {
            "female": voice_pack_status("female"),
            "male": voice_pack_status("male"),
        },
        "route_matrix": route_matrix,
        "taxonomy_summary": _taxonomy_summary(),
        "manual_acceptance_steps": [
            "Confirm exactly one external USB camera is selected.",
            "Confirm exactly one eligible USB/Arduino UART port is selected.",
            "Ping UART and require PONG.",
            "Use Admin/Desktop test mode to test O, R, I one by one; require ACK and correct servo direction.",
            "Select Loa laptop and preview startup/O/R/I/warning MP3; preview must not move servo.",
            "Run camera AI with actuation OFF; verify route logs only.",
            "Enable actuation/test mode and sort one object at a time; verify class, command, bin, audio, payload, ACK.",
        ],
    }


def write_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"{stamp}-hardware-acceptance.json"
    md_path = output_dir / f"{stamp}-hardware-acceptance.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, md_path


def _payload(command: str, protocol: str) -> str:
    try:
        return encode_sort(command, 0.99, protocol=protocol).decode("utf-8").strip()
    except Exception as e:
        return f"invalid:{e}"


def _taxonomy_summary() -> dict[str, Any]:
    counts: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    for cls_name in TRAINING_CLASS_ORDER_45:
        category = category_for_class(cls_name)
        code = category.code if category is not None else "other"
        counts[code] = counts.get(code, 0) + 1
        examples.setdefault(code, [])
        if len(examples[code]) < 8:
            examples[code].append(cls_name)
    return {"counts": counts, "examples": examples}


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Hardware Acceptance Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Safe mode: {report['safe_mode']}",
        f"- Profile: {report['hardware_profile']['profile_id']}",
        f"- UART: {report['config']['uart_port'] or 'not selected'} @ {report['config']['uart_baud']} {report['config']['uart_protocol']}",
        f"- Speaker: {report['config']['speaker_output_mode']} / {report['config']['voice_gender']}",
        "",
        "## Route Matrix",
        "",
        "| Command | Category | Bin | Payload | Laptop event | Laptop file | Hardware track |",
        "|---|---|---:|---|---|---|---:|",
    ]
    for item in report["route_matrix"]:
        lines.append(
            "| {command} | {category} | {bin_index} | {uart_payload} | {laptop_audio_event} | {laptop_audio_file} | {hardware_track} |".format(
                **{key: "" if value is None else value for key, value in item.items()}
            )
        )
    lines.extend(
        [
            "",
            "## Devices",
            "",
            f"- Eligible USB/Arduino UART ports: {len(report['devices']['eligible_usb_serial_ports'])}",
            f"- External USB cameras: {len(report['devices']['external_usb_cameras'])}",
            "",
            "## Manual Acceptance Steps",
            "",
        ]
    )
    lines.extend(f"{index}. {step}" for index, step in enumerate(report["manual_acceptance_steps"], start=1))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    _configure_console_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "audit" / "hardware")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report()
    json_path, md_path = write_report(report, args.output_dir)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Hardware acceptance report written:\n- {json_path}\n- {md_path}")
    return 0


def _configure_console_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
