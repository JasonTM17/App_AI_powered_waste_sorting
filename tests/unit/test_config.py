import json
from pathlib import Path

import pytest

from app.core.config import AppConfig, load_config, save_config


def _default_dict():
    return {
        "camera": {"source": "0", "width": 1280, "height": 720, "mirror": False},
        "model": {
            "path": "models/best.pt",
            "device": "cpu",
            "conf_threshold": 0.4,
            "iou_threshold": 0.45,
            "input_size": 640,
            "half_precision": False,
        },
        "uart": {"port": "COM3", "baud": 9600, "auto_reconnect": True, "ack_timeout_ms": 200},
        "mappings": [{"class_name": "plastic", "command": "S", "bin_index": 2, "enabled": True}],
        "roi": {"enabled": False, "x": 0, "y": 0, "width": 0, "height": 0},
        "capture": {"mode": "auto_low_conf", "low_conf_threshold": 0.6, "output_dir": "dataset_v2"},
        "theme": "dark",
        "language": "vi",
        "minimize_to_tray": True,
        "autostart": False,
    }


def test_app_config_parses_default_dict():
    c = AppConfig.model_validate(_default_dict())
    assert c.camera.source == "0"
    assert c.model.conf_threshold == 0.4
    assert c.uart.port == "COM3"
    assert c.mappings[0].command == "S"


def test_conf_threshold_out_of_range_rejected():
    d = _default_dict()
    d["model"]["conf_threshold"] = 1.5
    with pytest.raises(Exception):
        AppConfig.model_validate(d)


def test_save_and_load_roundtrip(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg = AppConfig.model_validate(_default_dict())
    save_config(cfg, cfg_path)
    assert cfg_path.exists()
    loaded = load_config(cfg_path)
    assert loaded.camera.source == cfg.camera.source
    assert loaded.mappings[0].command == "S"


def test_load_missing_file_writes_default(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    assert cfg_path.exists()
    assert isinstance(cfg, AppConfig)


def test_load_corrupt_json_backs_up_and_writes_default(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{ not valid json", encoding="utf-8")
    cfg = load_config(cfg_path)
    assert isinstance(cfg, AppConfig)
    assert (cfg_path.parent / "config.json.broken").exists()


def test_atomic_save_does_not_corrupt(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg = AppConfig.model_validate(_default_dict())
    save_config(cfg, cfg_path)
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert raw["camera"]["source"] == "0"
    assert not (tmp_path / "config.json.tmp").exists()
