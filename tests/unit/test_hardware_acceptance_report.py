from pathlib import Path

from scripts import hardware_acceptance_report as report_module


def test_hardware_acceptance_report_uses_canonical_route_matrix(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(
        report_module,
        "list_serial_ports",
        lambda: [{"device": "COM8", "name": "USB Serial", "hwid": "USB VID:2341", "is_usb": True}],
    )
    monkeypatch.setattr(report_module, "list_pnp_cameras", lambda: [])

    report = report_module.build_report()

    routes = {item["command"]: item for item in report["route_matrix"]}
    assert routes["O"]["bin_index"] == 1
    assert routes["O"]["serial_payload"] == "huuco"
    assert routes["O"]["hardware_track"] == 2
    assert routes["R"]["bin_index"] == 2
    assert routes["R"]["serial_payload"] == "voco"
    assert routes["R"]["hardware_track"] == 4
    assert routes["I"]["bin_index"] == 3
    assert routes["I"]["serial_payload"] == "taiche"
    assert routes["I"]["hardware_track"] == 3
    assert report["safe_mode"] is True


def test_hardware_acceptance_report_writes_markdown_and_json(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(report_module, "list_serial_ports", lambda: [])
    monkeypatch.setattr(report_module, "list_pnp_cameras", lambda: [])

    report = report_module.build_report()
    json_path, md_path = report_module.write_report(report, tmp_path / "audit")

    assert json_path.exists()
    assert md_path.exists()
    text = Path(md_path).read_text(encoding="utf-8")
    assert "Route Matrix" in text
    assert "sort_R" in text
