import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.config import AppConfig
from app.ui.pages.capture import CapturePage


def test_capture_page_exposes_pen_for_manual_camera_capture(tmp_path, qtbot):
    cfg = AppConfig()
    cfg.capture.output_dir = str(tmp_path / "dataset")
    page = CapturePage(cfg)
    page._catalog_path = tmp_path / "dataset.db"
    qtbot.addWidget(page)

    assert page.class_select.findText("Pen") >= 0
    assert page.capture_camera_sample_requested is not None
