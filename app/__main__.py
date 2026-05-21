"""Entry point: python -m app."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.config import load_config
from app.ui.controller import AppController
from app.ui.main_window import MainWindow
from app.ui.widgets.theme import apply_theme
from app.utils.logging import logger, setup_logging
from app.utils.paths import config_path, db_path


def main() -> int:
    setup_logging()
    logger.info("starting app")
    app = QApplication(sys.argv)
    app.setApplicationName("Trash Sorter Pro")
    app.setOrganizationName("TrashSorter")

    cfg_path = config_path()
    cfg = load_config(cfg_path)
    apply_theme(app, cfg.theme)

    window = MainWindow(cfg)
    controller = AppController(cfg, cfg_path, db_path())

    controller.uart_status.connect(window.live_page.set_uart_status)
    if window.settings_page is not None:
        window.settings_page.config_saved.connect(controller.update_config)
    if window.mapping_page is not None:
        def _on_mappings(lst):
            new_cfg = controller.cfg.model_copy(deep=True)
            new_cfg.mappings = lst
            controller.update_config(new_cfg)
        window.mapping_page.mappings_saved.connect(_on_mappings)

    def _on_frame(frame, detections, fps, latency):
        window.live_page.update_frame(frame, detections)
        window.live_page.set_fps(fps)
        window.live_page.set_latency(latency)

    controller.frame_processed.connect(_on_frame)

    window.show()
    controller.start()
    rc = app.exec()
    controller.stop()
    return rc


if __name__ == "__main__":
    sys.exit(main())
