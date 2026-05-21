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
    if window.settings_page is not None:
        window.settings_page.test_camera_requested.connect(controller.test_camera)
        window.settings_page.test_uart_requested.connect(controller.test_uart_ping)
        window.settings_page.reload_model_requested.connect(controller.reload_model)
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
    window.live_page.snapshot_requested.connect(controller.take_snapshot)

    window.show()

    from PySide6.QtWidgets import QSystemTrayIcon
    from app.ui.widgets.tray import TrayIcon
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = TrayIcon(window)
        tray.show()
        tray.show_requested.connect(window.show)
        tray.show_requested.connect(window.activateWindow)
        tray.quit_requested.connect(window.force_quit)
        window.tray = tray
        window._minimize_to_tray = cfg.minimize_to_tray
        controller.uart_status.connect(
            lambda ok: tray.notify("UART", "Mất kết nối" if not ok else "Đã kết nối")
            if not ok else None
        )

    controller.start()

    history_service = controller.history
    if history_service is not None:
        from app.ui.pages.history import HistoryPage
        hp = HistoryPage(history_service)
        old = window.stack.widget(1)
        window.stack.insertWidget(1, hp)
        window.stack.removeWidget(old)
        window.history_page = hp

    rc = app.exec()
    controller.stop()
    return rc


if __name__ == "__main__":
    sys.exit(main())
