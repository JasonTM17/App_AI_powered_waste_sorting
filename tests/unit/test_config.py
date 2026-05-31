import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import (
    MULTI_CLASS_WARNING_TEXT,
    AppConfig,
    load_config,
    merge_missing_mappings,
    save_config,
    startup_hardware_speaker_config,
)


def _default_dict():
    return {
        "camera": {
            "source": "",
            "width": 1280,
            "height": 720,
            "mirror": False,
            "rotation": 0,
        },
        "model": {
            "path": "models/best.pt",
            "device": "auto",
            "conf_threshold": 0.4,
            "iou_threshold": 0.45,
            "input_size": 640,
            "half_precision": False,
        },
        "uart": {
            "port": "",
            "baud": 9600,
            "auto_reconnect": True,
            "ack_timeout_ms": 4500,
            "protocol": "plain_group",
        },
        "mappings": [{"class_name": "plastic", "command": "S", "bin_index": 2, "enabled": True}],
        "roi": {"enabled": False, "x": 0, "y": 0, "width": 0, "height": 0},
        "capture": {"mode": "auto_low_conf", "low_conf_threshold": 0.6, "output_dir": "dataset_v2"},
        "speaker": {
            "enabled": False,
            "output_mode": "hardware",
            "voice_gender": "female",
            "cooldown_seconds": 2.5,
        },
        "dispatch_guard": {
            "min_sort_interval_seconds": 12.0,
            "busy_settle_seconds": 1.0,
            "min_stable_frames": 3,
            "empty_rearm_seconds": 2.0,
            "empty_rearm_frames": 10,
            "require_roi_for_dispatch": True,
            "max_objects_per_dispatch": 1,
            "max_classes_per_dispatch": 1,
            "multi_class_warning_cooldown_seconds": 5.0,
            "multi_class_warning_text": MULTI_CLASS_WARNING_TEXT,
            "multi_class_warning_audio_track": 8,
        },
        "three_bin_classifier": {
            "enabled": False,
            "model_path": "models/three_bin_classifier.pt",
            "min_confidence": 0.72,
            "min_margin": 0.12,
            "unknown_only": True,
            "min_crop_area_ratio": 0.003,
            "input_size": 224,
        },
        "theme": "dark",
        "language": "vi",
        "minimize_to_tray": True,
        "autostart": False,
    }


def test_app_config_parses_default_dict():
    c = AppConfig.model_validate(_default_dict())
    assert c.camera.source == ""
    assert c.camera.rotation == 0
    assert c.model.conf_threshold == 0.4
    assert c.uart.port == ""
    assert c.uart.protocol == "plain_group"
    assert c.speaker.enabled is False
    assert c.speaker.output_mode == "hardware"
    assert c.speaker.cooldown_seconds == 2.5
    assert c.unknown_fallback.enabled is True
    assert c.unknown_fallback.dispatch_enabled is False
    assert c.unknown_fallback.command == "R"
    assert c.unknown_fallback.bin_index == 2
    assert c.dispatch_guard.min_sort_interval_seconds == 12.0
    assert c.dispatch_guard.require_roi_for_dispatch is True
    assert c.dispatch_guard.max_objects_per_dispatch == 1
    assert c.dispatch_guard.max_classes_per_dispatch == 1
    assert c.dispatch_guard.multi_class_warning_cooldown_seconds == 5.0
    assert c.dispatch_guard.multi_class_warning_text == MULTI_CLASS_WARNING_TEXT
    assert c.dispatch_guard.multi_class_warning_audio_track == 8
    assert c.manual_reference_recognition.enabled is True
    assert c.manual_reference_recognition.min_similarity == 0.82
    assert c.manual_reference_recognition.min_consensus_similarity == 0.55
    assert c.manual_reference_recognition.min_votes == 3
    assert c.manual_reference_recognition.top_k == 5
    assert c.manual_reference_recognition.cache_refresh_seconds == 30.0
    assert c.manual_reference_recognition.query_cache_seconds == 1.0
    assert c.manual_reference_recognition.correctable_yolo_classes == ["Cardboard"]
    assert c.manual_reference_recognition.correction_target_classes == ["Textile"]
    assert c.manual_reference_recognition.min_correction_area_ratio == 0.25
    assert c.three_bin_classifier.enabled is False
    assert c.three_bin_classifier.model_path == "models/three_bin_classifier.pt"
    assert c.three_bin_classifier.min_confidence == 0.72
    assert c.three_bin_classifier.min_margin == 0.12
    assert c.three_bin_classifier.unknown_only is True
    assert c.mappings[0].command == "S"


def test_conf_threshold_out_of_range_rejected():
    d = _default_dict()
    d["model"]["conf_threshold"] = 1.5
    with pytest.raises(ValidationError):
        AppConfig.model_validate(d)


def test_unknown_fallback_invalid_command_rejected():
    d = _default_dict()
    d["unknown_fallback"] = {"command": "", "bin_index": 2}
    with pytest.raises(ValidationError):
        AppConfig.model_validate(d)


def test_dispatch_guard_invalid_values_rejected():
    d = _default_dict()
    d["dispatch_guard"]["min_stable_frames"] = 0
    with pytest.raises(ValidationError):
        AppConfig.model_validate(d)


def test_manual_reference_recognition_invalid_values_rejected():
    d = _default_dict()
    d["manual_reference_recognition"] = {"min_similarity": 2.0}
    with pytest.raises(ValidationError):
        AppConfig.model_validate(d)
    d = _default_dict()
    d["manual_reference_recognition"] = {"min_correction_area_ratio": 1.5}
    with pytest.raises(ValidationError):
        AppConfig.model_validate(d)


def test_three_bin_classifier_invalid_values_rejected():
    d = _default_dict()
    d["three_bin_classifier"]["min_confidence"] = 1.5
    with pytest.raises(ValidationError):
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
    assert raw["camera"]["source"] == ""
    assert not (tmp_path / "config.json.tmp").exists()


def test_load_config_accepts_utf8_sig_and_clears_ambiguous_camera_index(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    data = _default_dict()
    data["camera"]["source"] = "0"
    cfg_path.write_text(json.dumps(data), encoding="utf-8-sig")

    cfg = load_config(cfg_path)

    assert cfg.camera.source == ""
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert raw["camera"]["source"] == ""


def test_load_config_clears_legacy_com3_when_not_usb(tmp_path: Path, monkeypatch):
    from app.utils import serial_enum

    monkeypatch.setattr(serial_enum, "list_serial_ports", lambda: [])
    cfg_path = tmp_path / "config.json"
    data = _default_dict()
    data["uart"]["port"] = "COM3"
    cfg_path.write_text(json.dumps(data), encoding="utf-8")

    cfg = load_config(cfg_path)

    assert cfg.uart.port == ""
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert raw["uart"]["port"] == ""


def test_load_config_repairs_plain_group_ack_timeout(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    data = _default_dict()
    data["uart"]["ack_timeout_ms"] = 200
    cfg_path.write_text(json.dumps(data), encoding="utf-8")

    cfg = load_config(cfg_path)

    assert cfg.uart.ack_timeout_ms == 4500
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert raw["uart"]["ack_timeout_ms"] == 4500


def test_load_config_replaces_legacy_multi_class_warning_text(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    data = _default_dict()
    data["dispatch_guard"]["multi_class_warning_text"] = "Số lượng rác bạn đặt chỉ nên là 1 loại."
    cfg_path.write_text(json.dumps(data), encoding="utf-8")

    cfg = load_config(cfg_path)

    assert cfg.dispatch_guard.multi_class_warning_text == MULTI_CLASS_WARNING_TEXT
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert raw["dispatch_guard"]["multi_class_warning_text"] == MULTI_CLASS_WARNING_TEXT


def test_load_config_keeps_legacy_enabled_speaker_on_hardware_default(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    data = _default_dict()
    data["speaker"] = {"enabled": True, "cooldown_seconds": 2.5}
    cfg_path.write_text(json.dumps(data), encoding="utf-8")

    cfg = load_config(cfg_path)

    assert cfg.speaker.enabled is False
    assert cfg.speaker.output_mode == "hardware"
    assert cfg.speaker.voice_gender == "female"
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert raw["speaker"]["enabled"] is False
    assert raw["speaker"]["output_mode"] == "hardware"
    assert raw["speaker"]["voice_gender"] == "female"


def test_load_config_enables_speaker_when_computer_speaker_mode_selected(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    data = _default_dict()
    data["speaker"] = {
        "enabled": False,
        "output_mode": "computer_speaker",
        "voice_gender": "male",
        "cooldown_seconds": 2.5,
    }
    cfg_path.write_text(json.dumps(data), encoding="utf-8")

    cfg = load_config(cfg_path)

    assert cfg.speaker.enabled is True
    assert cfg.speaker.output_mode == "computer_speaker"
    assert cfg.speaker.voice_gender == "male"


def test_startup_hardware_speaker_config_preserves_laptop_voice_choice():
    cfg = AppConfig()
    cfg.speaker.output_mode = "computer_speaker"
    cfg.speaker.enabled = True
    cfg.speaker.voice_gender = "male"
    cfg.speaker.cooldown_seconds = 4.5

    out = startup_hardware_speaker_config(cfg)

    assert out.speaker.output_mode == "hardware"
    assert out.speaker.enabled is False
    assert out.speaker.voice_gender == "male"
    assert out.speaker.cooldown_seconds == 4.5


def test_load_config_keeps_default_audio_output_on_hardware(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    data = _default_dict()
    cfg_path.write_text(json.dumps(data), encoding="utf-8")

    cfg = load_config(cfg_path)

    assert cfg.speaker.enabled is False
    assert cfg.speaker.output_mode == "hardware"


def test_load_config_persists_new_default_fields_for_legacy_file(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    data = _default_dict()
    data["speaker"].pop("voice_gender")
    data["unknown_fallback"] = {
        "enabled": True,
        "class_name": "Unknown object",
        "command": "R",
        "bin_index": 2,
        "min_raw_confidence": 0.05,
        "min_area_ratio": 0.003,
        "stable_frames": 2,
        "warmup_frames": 6,
    }
    data["dispatch_guard"].pop("max_objects_per_dispatch")
    cfg_path.write_text(json.dumps(data), encoding="utf-8")

    cfg = load_config(cfg_path)

    assert cfg.speaker.voice_gender == "female"
    assert cfg.unknown_fallback.dispatch_enabled is False
    assert cfg.dispatch_guard.max_objects_per_dispatch == 1
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert raw["speaker"]["voice_gender"] == "female"
    assert raw["unknown_fallback"]["dispatch_enabled"] is False
    assert raw["dispatch_guard"]["max_objects_per_dispatch"] == 1


def test_load_config_repairs_known_class_semantic_mappings(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    data = _default_dict()
    data["mappings"] = [
        {"class_name": "Paper", "command": "R", "bin_index": 2, "enabled": True},
        {
            "class_name": "Disposable tableware",
            "command": "I",
            "bin_index": 3,
            "enabled": True,
        },
        {"class_name": "Organic", "command": "O", "bin_index": 1, "enabled": True},
        {"class_name": "Pen", "command": "I", "bin_index": 3, "enabled": True},
    ]
    cfg_path.write_text(json.dumps(data), encoding="utf-8")

    cfg = load_config(cfg_path)

    by_name = {mapping.class_name: mapping for mapping in cfg.mappings}
    assert (by_name["Paper"].command, by_name["Paper"].bin_index) == ("I", 3)
    assert (
        by_name["Disposable tableware"].command,
        by_name["Disposable tableware"].bin_index,
    ) == ("R", 2)
    assert (by_name["Organic"].command, by_name["Organic"].bin_index) == ("O", 1)
    assert (by_name["Pen"].command, by_name["Pen"].bin_index) == ("R", 2)

    saved = json.loads(cfg_path.read_text(encoding="utf-8"))
    saved_by_name = {mapping["class_name"]: mapping for mapping in saved["mappings"]}
    assert saved_by_name["Paper"]["command"] == "I"
    assert saved_by_name["Disposable tableware"]["command"] == "R"


def test_merge_missing_mappings_keeps_user_edits():
    cfg = AppConfig(
        mappings=[
            {
                "class_name": "Paper",
                "command": "X",
                "bin_index": 9,
                "enabled": False,
            }
        ]
    )
    seed = AppConfig(
        mappings=[
            {"class_name": "Paper", "command": "P", "bin_index": 1, "enabled": True},
            {"class_name": "Plastic", "command": "S", "bin_index": 2, "enabled": True},
        ]
    )

    merged, changed = merge_missing_mappings(cfg, seed)

    assert changed is True
    assert len(merged.mappings) == 2
    assert merged.mappings[0].class_name == "Paper"
    assert merged.mappings[0].command == "X"
    assert merged.mappings[0].bin_index == 9
    assert merged.mappings[0].enabled is False
    assert merged.mappings[1].class_name == "Plastic"
