"""Entry point: python -m app."""

from __future__ import annotations

import os
import shutil
import sys

from PySide6.QtWidgets import QApplication

from app.core.config import load_config
from app.ui.controller import AppController
from app.ui.live_status import live_ack_status_text, multi_object_warning_text
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
    app.setWindowIcon(_app_icon())

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
    web_launchers = []

    controller.uart_status.connect(window.live_page.set_uart_status)
    controller.uart_status.connect(window.set_uart_status)
    controller.camera_status.connect(window.set_camera_status)
    controller.camera_status.connect(window.live_page.set_camera_on)
    controller.camera_status.connect(window.title_bar.set_camera_on)
    controller.model_status.connect(window.set_model_status)

    def _sync_speaker_output_mode(mode: str) -> None:
        window.live_page.set_speaker_output_mode(mode)
        if window.settings_page is not None:
            window.settings_page.audio_section.set_output_mode(mode)

    def _on_camera_request(on: bool):
        if on:
            controller.start_camera()
        else:
            controller.stop_camera()

    window.live_page.camera_toggled.connect(_on_camera_request)
    window.title_bar.camera_toggled.connect(_on_camera_request)

    def _sync_actuation_test_mode(enabled: bool) -> None:
        window.live_page.set_actuation_test_mode(enabled)
        if window.settings_page is not None:
            window.settings_page.set_actuation_test_mode(enabled)

    def _on_actuation_test_mode_request(enabled: bool) -> None:
        controller.set_actuation_test_mode(enabled)
        _sync_actuation_test_mode(controller.is_actuation_test_mode_enabled())

    window.live_page.actuation_test_mode_toggled.connect(_on_actuation_test_mode_request)

    def _on_speaker_output_mode_request(mode: str) -> None:
        new_cfg = controller.cfg.model_copy(deep=True)
        new_cfg.speaker.output_mode = mode
        controller.update_config(new_cfg)
        _sync_speaker_output_mode(controller.cfg.speaker.output_mode)

    window.live_page.speaker_output_mode_changed.connect(_on_speaker_output_mode_request)

    def _open_web_dashboard(tab: str = "live") -> None:
        from PySide6.QtCore import QPoint, QUrl
        from PySide6.QtGui import QDesktopServices

        from app.ui.web_launcher import WebLauncherThread
        from app.ui.widgets.toast import Toast

        t = Toast(window, "Đang bật web dashboard…", level="info", duration_ms=2500)
        tr = window.mapToGlobal(QPoint(window.width(), 0))
        t.show_at(window.mapFromGlobal(tr))

        worker = WebLauncherThread()
        web_launchers.append(worker)

        def _done(ok: bool, message: str, url: str) -> None:
            final_url = url.split("?", 1)[0] + f"?tab={tab}"
            level = "ok" if ok else "warn"
            Toast(window, message, level=level, duration_ms=5000).show_at(window.mapFromGlobal(tr))
            if ok:
                QDesktopServices.openUrl(QUrl(final_url))

        worker.done.connect(_done)
        worker.finished.connect(lambda: web_launchers.remove(worker) if worker in web_launchers else None)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    window.title_bar.web_requested.connect(lambda: _open_web_dashboard("live"))

    def _on_camera_error(msg: str):
        from PySide6.QtCore import QPoint

        from app.ui.widgets.toast import Toast
        t = Toast(window, msg, level="warn", duration_ms=5000)
        tr = window.mapToGlobal(QPoint(window.width(), 0))
        t.show_at(window.mapFromGlobal(tr))

    controller.camera_error.connect(_on_camera_error)
    if window.settings_page is not None:
        def _on_config_saved(new_cfg):
            apply_theme(app, new_cfg.theme)
            controller.update_config(new_cfg)
            _sync_speaker_output_mode(controller.cfg.speaker.output_mode)
            from PySide6.QtCore import QPoint

            from app.ui.widgets.toast import Toast
            t = Toast(window, "Đã lưu cài đặt", level="ok")
            tr = window.mapToGlobal(QPoint(window.width(), 0))
            t.show_at(window.mapFromGlobal(tr))

        window.settings_page.config_saved.connect(_on_config_saved)
    if window.settings_page is not None:
        window.settings_page.test_camera_requested.connect(controller.test_camera)
        window.settings_page.test_uart_requested.connect(controller.test_uart_ping)
        window.settings_page.test_hardware_requested.connect(controller.test_hardware_command)
        window.settings_page.test_voice_requested.connect(controller.test_laptop_voice)
        window.settings_page.actuation_test_mode_changed.connect(_on_actuation_test_mode_request)
        window.settings_page.reload_model_requested.connect(controller.reload_model)
        controller.test_uart_result.connect(window.settings_page.set_uart_test_result)
        _sync_actuation_test_mode(controller.is_actuation_test_mode_enabled())
        _sync_speaker_output_mode(controller.cfg.speaker.output_mode)
    if window.mapping_page is not None:

        def _on_mappings(lst):
            new_cfg = controller.cfg.model_copy(deep=True)
            new_cfg.mappings = lst
            controller.update_config(new_cfg)

        window.mapping_page.mappings_saved.connect(_on_mappings)
        window.mapping_page.test_command_requested.connect(
            lambda cmd: controller.test_hardware_command(
                controller.cfg.uart.port,
                controller.cfg.uart.baud,
                cmd,
            )
        )

    def _on_test_result(ok: bool, message: str) -> None:
        from PySide6.QtCore import QPoint

        from app.ui.widgets.toast import Toast

        level = "ok" if ok else "warn"
        tr = window.mapToGlobal(QPoint(window.width(), 0))
        Toast(window, message, level=level, duration_ms=4500).show_at(window.mapFromGlobal(tr))

    controller.test_camera_result.connect(_on_test_result)
    controller.test_uart_result.connect(_on_test_result)
    controller.reload_model_result.connect(_on_test_result)
    controller.snapshot_saved.connect(_on_test_result)

    def _on_frame(frame, detections, fps, latency):
        window.live_page.update_frame(frame, detections)
        window.live_page.set_fps(fps)
        window.live_page.set_latency(latency)
        window.set_fps(fps)
        guard_status = controller.dispatch_status()
        warning_text = multi_object_warning_text(
            guard_status,
            controller.cfg.dispatch_guard.multi_class_warning_text,
        )
        window.live_page.set_warning(warning_text)
        # Push each detection into the side stream so user can see what
        # the model classified (= app cũ's "system log under camera")
        if detections:
            from datetime import datetime

            from app.core.config import ClassMapping
            from app.core.uart_protocol import encode_sort
            from app.core.waste_categories import (
                category_for_command,
                normalize_mapping_to_three_bins,
            )

            ts = datetime.now().strftime("%H:%M:%S")
            for d in detections:
                mapping = next(
                    (m for m in controller.cfg.mappings if m.enabled and m.class_name == d.cls_name),
                    None,
                )
                fallback = controller.cfg.unknown_fallback
                if mapping is None and d.cls_name == fallback.class_name:
                    mapping = ClassMapping(
                        class_name=fallback.class_name,
                        command=fallback.command,
                        bin_index=fallback.bin_index,
                        enabled=True,
                    )
                detail = "no mapping"
                if mapping is not None:
                    mapping = normalize_mapping_to_three_bins(mapping)
                    category = category_for_command(mapping.command)
                    if category is None:
                        continue
                    command = category.code
                    bin_index = category.bin_index
                    try:
                        payload = encode_sort(
                            command,
                            d.conf,
                            protocol=controller.cfg.uart.protocol,
                        ).decode("utf-8").strip()
                    except ValueError:
                        payload = "-"
                    test_mode_enabled = controller.is_actuation_test_mode_enabled()
                    ack = live_ack_status_text(
                        test_mode_enabled=test_mode_enabled,
                        dispatch_status=guard_status,
                        uart_connected=controller.is_uart_connected(),
                        multi_class_warning_text=controller.cfg.dispatch_guard.multi_class_warning_text,
                    )
                    mode = "TEST ON" if test_mode_enabled else "TEST OFF"
                    detail = (
                        f"{mode}; {category.name}; bin {bin_index}; "
                        f"payload {payload}; ACK {ack}"
                    )
                window.live_page.append_detection(d.cls_name, d.conf, ts, detail)

    controller.frame_processed.connect(_on_frame)
    window.live_page.snapshot_requested.connect(controller.take_snapshot)
    if window.capture_page is not None:
        window.capture_page.open_web_requested.connect(lambda: _open_web_dashboard("data"))
        window.capture_page.capture_camera_sample_requested.connect(controller.capture_camera_sample)
        controller.capture_saved.connect(lambda _p: window.capture_page.reload())

        def _on_capture_mode_changed(mode: str):
            new_cfg = controller.cfg.model_copy(deep=True)
            new_cfg.capture.mode = mode
            controller.update_config(new_cfg)

        window.capture_page.mode_changed.connect(_on_capture_mode_changed)

    window.show()

    from PySide6.QtWidgets import QSystemTrayIcon

    from app.ui.widgets.tray import TrayIcon

    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = TrayIcon(window, app.windowIcon())
        tray.show()
        tray.show_requested.connect(window.show)
        tray.show_requested.connect(window.activateWindow)
        tray.quit_requested.connect(window.force_quit)
        window.tray = tray
        window._minimize_to_tray = cfg.minimize_to_tray
        uart_tray_state = {"was_connected": False}

        def _notify_uart_disconnect(ok: bool) -> None:
            if ok:
                uart_tray_state["was_connected"] = True
                return
            if not uart_tray_state["was_connected"]:
                return
            uart_tray_state["was_connected"] = False
            tray.notify("UART", "Mất kết nối")

        controller.uart_status.connect(_notify_uart_disconnect)

    controller.start()
    if os.environ.get("TRASH_SORTER_AUTOSTART_CAMERA") == "1":
        from PySide6.QtCore import QTimer

        QTimer.singleShot(700, controller.start_camera)

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


def _app_icon():
    from app.ui.brand_assets import brand_icon

    return brand_icon()


if __name__ == "__main__":
    sys.exit(main())
