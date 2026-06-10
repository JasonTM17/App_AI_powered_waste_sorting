import json
import sys

from scripts import preflight_runtime


def test_preflight_report_declares_real_hardware_optional(monkeypatch, tmp_path, capsys):
    model = tmp_path / "best.pt"
    model.write_bytes(b"model")

    def fake_get_json(url):
        if url.endswith("/api/dataset/summary"):
            return {"images": 0, "boxes": 0, "needs_sync": False}
        if url.endswith("/api/status"):
            return {"camera": {"message": "not connected"}, "uart": {"message": "not connected"}}
        return {"ok": True, "app": "agent"}

    monkeypatch.setattr(sys, "argv", ["preflight_runtime.py", "--json", "--model", str(model)])
    monkeypatch.setattr(preflight_runtime, "_get_json", fake_get_json)
    monkeypatch.setattr(preflight_runtime, "_http_ok", lambda url: {"ok": True, "status": 200})
    monkeypatch.setattr(preflight_runtime, "_gpu_summary", lambda: {"error": "not available"})
    monkeypatch.setattr(
        preflight_runtime,
        "_operations_summary",
        lambda: {"ok": True, "station_total": 10, "bin_total": 30, "seed_source": "seed"},
    )
    monkeypatch.setattr(preflight_runtime, "_lock_summary", lambda fix_stale: {"items": [], "cleaned": []})

    rc = preflight_runtime.main()
    report = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert report["hardware"]["mode"] == "software_safety_only"
    assert report["hardware"]["real_hardware_required"] is False
    assert report["hardware"]["camera_required"] is False
    assert report["hardware"]["uart_required"] is False
    assert report["operations"]["ok"] is True
