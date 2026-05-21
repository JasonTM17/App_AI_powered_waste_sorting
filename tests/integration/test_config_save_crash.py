import json
from pathlib import Path

import pytest

from app.core import config as config_mod
from app.core.config import AppConfig, save_config


def test_save_keeps_original_when_tmp_write_fails(tmp_path: Path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    original = AppConfig()
    save_config(original, cfg_path)
    raw_before = cfg_path.read_text(encoding="utf-8")

    real_replace = config_mod.os.replace

    def fake_replace(src, dst):
        raise OSError("simulated crash mid-rename")

    monkeypatch.setattr(config_mod.os, "replace", fake_replace)

    bad = original.model_copy(deep=True)
    bad.theme = "light"
    with pytest.raises(OSError):
        save_config(bad, cfg_path)

    raw_after = cfg_path.read_text(encoding="utf-8")
    assert raw_after == raw_before, "original config must be preserved when rename fails"

    monkeypatch.setattr(config_mod.os, "replace", real_replace)


def test_save_overwrites_on_success(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    a = AppConfig()
    save_config(a, cfg_path)
    b = a.model_copy(deep=True)
    b.theme = "light"
    save_config(b, cfg_path)
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert raw["theme"] == "light"
    assert not (cfg_path.parent / "config.json.tmp").exists()
