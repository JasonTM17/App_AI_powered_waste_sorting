import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.config import AppConfig
from app.ui.pages.settings import SettingsPage


def test_settings_emits_config_on_save(qtbot):
    cfg = AppConfig()
    page = SettingsPage(cfg)
    qtbot.addWidget(page)
    captured = []
    page.config_saved.connect(lambda c: captured.append(c))
    page.mdl_conf.setValue(50)
    page._save()
    assert captured
    assert abs(captured[0].model.conf_threshold - 0.5) < 1e-6


def test_settings_collect_carries_camera_source(qtbot):
    cfg = AppConfig()
    page = SettingsPage(cfg)
    qtbot.addWidget(page)
    page.cam_source.setText("rtsp://x")
    out = page._collect()
    assert out.camera.source == "rtsp://x"
