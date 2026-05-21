"""Entry point: python -m app."""

from __future__ import annotations

import shutil
import sys

from PySide6.QtWidgets import QApplication

from app.core.config import load_config
from app.ui.controller import AppController
from app.ui.main_window import MainWindow
from app.ui.widgets.theme import apply_theme
from app.utils.logging import logger, setup_logging
from app.utils.paths import config_path, db_path, example_config_path


def _seed_config_if_missing() -> None:
    """Copy bundled `config.example.json` to user config on first run.

    Without this, the user gets an empty `mappings: []` default and the
    Mapping tab shows nothing. The example bundles all 42 model classes.
    """
    target = config_path()
    if target.exists():
        return
    seed = example_config_path()
    if not seed.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed, target)
    logger.info("seeded config from {}", seed)


def main() -> int:
    setup_logging()
    logger.info("starting app")
    app = QApplication(sys.argv)
    app.setApplicationName("Trash Sorter Pro")
    app.setOrganizationName("TrashSorter")

    _seed_config_if_missing()
    cfg_path = config_path()
    cfg = load_config(cfg_path)
    apply_theme(app, cfg.theme)

    from app.utils.i18n import install_translator

    install_translator(app, cfg.language)

    from app.ui.widgets.splash import Splash

    splash = Splash("Khởi tạo…")
    splash.show()
    app.processEvents()

    splash.set_message("Loading model…")
    app.processEvents()

    window = MainWindow(cfg)
    controller = AppController(cfg, cfg_path, db_path())

    controller.uart_status.connect(window.live_page.set_uart_status)
    controller.uart_status.connect(window.set_uart_status)
    controller.camera_status.connect(window.set_camera_status)
    controller.model_status.connect(window.set_model_status)
    if window.settings_page is not None:
        def _on_config_saved(new_cfg):
            apply_theme(app, new_cfg.theme)
            controller.update_config(new_cfg)
            from PySide6.QtCore import QPoint
            from app.ui.widgets.toast import Toast
            t = Toast(window, "Đã lưu cài đặt", level="ok")
            tr = window.mapToGlobal(QPoint(window.width(), 0))
            t.show_at(window.mapFromGlobal(tr))

        window.settings_page.config_saved.connect(_on_config_saved)
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
        window.set_fps(fps)

    controller.frame_processed.connect(_on_frame)
    window.live_page.snapshot_requested.connect(controller.take_snapshot)
    if window.capture_page is not None:
        controller.capture_saved.connect(lambda _p: window.capture_page.reload())

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
            lambda ok: (
                tray.notify("UART", "Mất kết nối" if not ok else "Đã kết nối") if not ok else None
            )
        )

    controller.start()

    splash.finish(window)

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
