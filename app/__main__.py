"""Entry point: python -m app."""

from __future__ import annotations

import os
import shutil
import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.core.config import load_config, save_config, startup_hardware_speaker_config
from app.core.history import HistoryService
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


def main(*, require_admin_login: bool = True) -> int:
    setup_logging()
    startup_t0 = time.perf_counter()

    def _log_startup(marker: str) -> None:
        logger.info("startup_timing marker={} elapsed_ms={:.0f}", marker, (time.perf_counter() - startup_t0) * 1000)

    logger.info("starting app")
    app = QApplication(sys.argv)
    app.setApplicationName("Trash Sorter Pro" if require_admin_login else "Trash Sorter Pro Demo")
    app.setOrganizationName("TrashSorter")
    app.setWindowIcon(_app_icon())

    _seed_config_if_missing()
    cfg_path = config_path()
    cfg = load_config(cfg_path)
    startup_cfg = startup_hardware_speaker_config(cfg)
    if startup_cfg.speaker != cfg.speaker:
        cfg = startup_cfg
        save_config(cfg, cfg_path)
        logger.info("speaker output reset to hardware for desktop startup")
    apply_theme(app, cfg.theme)

    from app.utils.i18n import install_translator

    install_translator(app, cfg.language)

    from app.agent.operations_store import prewarm_operations_schema_async
    from app.utils.paths import operations_db_path

    if require_admin_login:
        from app.agent.auth_service import prewarm_auth_schema_async
        from app.utils.local_web import apply_local_auth_environment

        applied_auth_env = apply_local_auth_environment(allow_dev_defaults=True)
        if applied_auth_env:
            logger.info("desktop auth env loaded keys={}", sorted(applied_auth_env))
        prewarm_auth_schema_async()
    else:
        logger.warning("desktop demo mode enabled; admin login skipped")
    prewarm_operations_schema_async(
        operations_db_path(),
        device_defaults={
            "device_id": cfg.device.device_id,
            "device_name": cfg.device.device_name,
            "location": cfg.device.location,
            "owner_username": cfg.device.owner_username,
        },
    )
    _log_startup("auth_env_and_schema_prewarm_started")

    if require_admin_login:
        from app.ui.widgets.admin_login_dialog import AdminLoginDialog

        login = AdminLoginDialog()
        _log_startup("login_dialog_created")
        if login.exec() != 1:
            logger.info("desktop admin login cancelled")
            return 0
        logger.info(
            "desktop admin login accepted user={}",
            login.identity.username if login.identity else "",
        )
        _log_startup("desktop_admin_login_accepted")

    from app.ui.widgets.splash import Splash

    splash = Splash("Khởi tạo…")
    splash.show()
    app.processEvents()

    splash.set_message("Loading model…")
    app.processEvents()

    controller = AppController(cfg, cfg_path, db_path())
    history_service = HistoryService(db_path())
    window = MainWindow(cfg, history_service)
    _log_startup("main_window_created")
    web_launchers = []

    controller.uart_status.connect(window.live_page.set_uart_status)
    controller.uart_status.connect(window.set_uart_status)
    controller.camera_status.connect(window.set_camera_status)
    controller.camera_status.connect(window.live_page.set_camera_on)
    controller.camera_status.connect(window.title_bar.set_camera_on)
    controller.model_status.connect(window.set_model_status)

    def _sync_speaker_output_mode(mode: str) -> None:
        window.live_page.set_speaker_output_mode(mode)
        window.live_page.set_speaker_voice_gender(controller.cfg.speaker.voice_gender)
        if window.settings_page is not None:
            window.settings_page.audio_section.set_output_mode(mode)
            window.settings_page.audio_section.set_voice_gender(controller.cfg.speaker.voice_gender)

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

    controller.actuation_mode_changed.connect(_sync_actuation_test_mode)
    window.live_page.actuation_test_mode_toggled.connect(_on_actuation_test_mode_request)
    window.recognition_test_page.recognition_test_start_requested.connect(
        controller.start_recognition_test
    )
    window.recognition_test_page.recognition_test_pause_requested.connect(
        controller.pause_recognition_test
    )
    window.recognition_test_page.recognition_test_resume_requested.connect(
        controller.resume_recognition_test
    )
    window.recognition_test_page.recognition_test_abort_requested.connect(
        controller.abort_recognition_test
    )
    controller.recognition_test_state_changed.connect(
        window.recognition_test_page.set_recognition_test_state
    )
    controller.recognition_test_trial_saved.connect(
        window.recognition_test_page.set_recognition_test_trial
    )
    controller.recognition_test_action_result.connect(
        window.recognition_test_page.set_recognition_test_action_result
    )
    if window.history_page is not None:
        window.history_page.qa_promote_requested.connect(
            controller.promote_recognition_trial
        )
        controller.recognition_test_trial_saved.connect(
            lambda _trial: window.history_page.refresh_qa()
        )
        controller.recognition_test_action_result.connect(
            lambda _ok, _message: window.history_page.refresh_qa()
        )

    def _on_speaker_output_mode_request(mode: str) -> None:
        new_cfg = controller.cfg.model_copy(deep=True)
        new_cfg.speaker.output_mode = mode
        controller.update_config(new_cfg)
        _sync_speaker_output_mode(controller.cfg.speaker.output_mode)

    def _on_speaker_voice_gender_request(gender: str) -> None:
        new_cfg = controller.cfg.model_copy(deep=True)
        new_cfg.speaker.voice_gender = gender
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
    def _on_config_saved(new_cfg):
        apply_theme(app, new_cfg.theme)
        window.sidebar.set_theme(new_cfg.theme)
        controller.update_config(new_cfg)
        _sync_speaker_output_mode(controller.cfg.speaker.output_mode)
        from PySide6.QtCore import QPoint

        from app.ui.widgets.toast import Toast

        t = Toast(window, "Đã lưu cài đặt", level="ok")
        tr = window.mapToGlobal(QPoint(window.width(), 0))
        t.show_at(window.mapFromGlobal(tr))

    def _on_mappings(lst):
        new_cfg = controller.cfg.model_copy(deep=True)
        new_cfg.mappings = lst
        controller.update_config(new_cfg)

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
    controller.recognition_test_action_result.connect(_on_test_result)

    def _on_frame(frame, detections, fps, latency):
        window.live_page.update_frame(frame, detections)
        window.live_page.set_fps(fps)
        window.live_page.set_latency(latency)
        window.set_fps(fps)
        guard_status = controller.dispatch_status()
        window.live_page.set_dispatch_status(guard_status)
        window.live_page.set_auto_sort_state(controller.auto_sort_state())
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

    def _open_camera_annotation_dialog(target_page, cls_name: str, cls_id: int) -> None:
        from PySide6.QtWidgets import QMessageBox

        from app.ui.widgets.camera_annotation_dialog import CameraAnnotationDialog

        ok, message, frame, bbox = controller.camera_annotation_snapshot(cls_name)
        if not ok or frame is None:
            QMessageBox.warning(window, "Chưa có frame", message)
            return
        dialog = CameraAnnotationDialog(
            frame,
            class_name=cls_name,
            initial_bbox=bbox,
            parent=window,
        )
        if dialog.exec() != 1:
            return
        box = dialog.bbox_xyxy()
        if box is None:
            QMessageBox.warning(window, "Thiếu bbox", "Vui lòng kéo vẽ bbox trước khi lưu mẫu.")
            return
        target_page.capture_reviewed_camera_sample_requested.emit(
            cls_name,
            int(cls_id),
            box,
            dialog.approve_now(),
        )

    def _on_capture_mode_changed(mode: str):
        new_cfg = controller.cfg.model_copy(deep=True)
        new_cfg.capture.mode = mode
        controller.update_config(new_cfg)

    def _wire_settings_page(page) -> None:
        page.config_saved.connect(_on_config_saved)
        page.test_camera_requested.connect(controller.test_camera)
        page.test_uart_requested.connect(controller.test_uart_ping)
        page.test_hardware_requested.connect(controller.test_hardware_command)
        page.test_voice_requested.connect(controller.test_audio_event)
        page.speaker_output_mode_changed.connect(_on_speaker_output_mode_request)
        page.speaker_voice_gender_changed.connect(_on_speaker_voice_gender_request)
        page.actuation_test_mode_changed.connect(_on_actuation_test_mode_request)
        page.reload_model_requested.connect(controller.reload_model)
        controller.test_uart_result.connect(page.set_uart_test_result)
        _sync_actuation_test_mode(controller.is_actuation_test_mode_enabled())
        _sync_speaker_output_mode(controller.cfg.speaker.output_mode)

    def _wire_mapping_page(page) -> None:
        page.mappings_saved.connect(_on_mappings)
        page.test_command_requested.connect(
            lambda cmd: controller.test_hardware_command(
                controller.cfg.uart.port,
                controller.cfg.uart.baud,
                cmd,
            )
        )

    def _wire_capture_page(page) -> None:
        page.open_web_requested.connect(lambda: _open_web_dashboard("data"))
        page.capture_camera_sample_requested.connect(controller.capture_camera_sample)
        page.capture_hard_negative_requested.connect(controller.capture_hard_negative_sample)
        controller.capture_saved.connect(lambda _p, target=page: target.reload())
        page.mode_changed.connect(_on_capture_mode_changed)

    def _wire_training_page(page) -> None:
        page.open_web_requested.connect(lambda: _open_web_dashboard("training"))
        page.manual_phone_import_requested.connect(controller.import_manual_phone_samples)
        page.capture_camera_sample_requested.connect(controller.capture_camera_sample)
        page.capture_reviewed_camera_sample_requested.connect(
            controller.capture_reviewed_camera_sample
        )
        page.learn_now_status_requested.connect(controller.refresh_learn_now_status)
        page.learn_now_refresh_requested.connect(controller.refresh_learn_now_references)
        page.learn_now_train_requested.connect(controller.start_learn_now_candidate_training)
        page.training_stop_requested.connect(controller.stop_learn_now_training)
        page.training_status_requested.connect(controller.refresh_training_status)
        page.candidate_model_test_requested.connect(controller.load_candidate_model_for_test)
        controller.learn_now_status_changed.connect(page.set_learn_now_status)
        controller.learn_now_action_result.connect(page.set_learn_now_action_result)
        controller.training_status_changed.connect(page.set_training_status)
        controller.capture_saved.connect(lambda _p, target=page: target.reload())
        page.camera_annotation_requested.connect(
            lambda cls_name, cls_id, target=page: _open_camera_annotation_dialog(
                target, cls_name, cls_id
            )
        )

    def _wire_lazy_page(index: int, page) -> None:
        if index == 2:
            _wire_mapping_page(page)
        elif index == 3:
            _wire_capture_page(page)
        elif index == 4:
            _wire_training_page(page)
        elif index == 6:
            _wire_settings_page(page)

    window.page_created.connect(_wire_lazy_page)

    def _place_startup_window() -> None:
        if not getattr(window, "_user_minimized", False):
            window.ensure_visible_on_screen(center=True)

    window.show()
    for delay_ms in (0, 250, 1000):
        QTimer.singleShot(delay_ms, _place_startup_window)

    from PySide6.QtWidgets import QSystemTrayIcon

    from app.ui.widgets.tray import TrayIcon

    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = TrayIcon(window, app.windowIcon())
        tray.show()
        tray.show_requested.connect(window.restore_window)
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
    _log_startup("controller_started")
    if os.environ.get("TRASH_SORTER_AUTOSTART_CAMERA") == "1":
        QTimer.singleShot(700, controller.start_camera)

    splash.finish(window)
    _place_startup_window()
    _log_startup("main_window_shown")

    rc = 0
    try:
        rc = app.exec()
    finally:
        controller.stop()
        history_service.close()
    return rc


def _app_icon():
    from app.ui.brand_assets import brand_icon

    return brand_icon()


if __name__ == "__main__":
    sys.exit(main())
