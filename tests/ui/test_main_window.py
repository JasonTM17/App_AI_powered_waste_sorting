import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QAbstractScrollArea, QLabel, QPushButton, QSizePolicy

from app.core.config import AppConfig
from app.core.history import HistoryService
from app.ui.main_window import NAV_ITEMS, MainWindow
from app.ui.pages.capture import CapturePage
from app.ui.pages.training import TrainingPage
from app.ui.widgets.empty_state import EmptyState


def test_main_window_no_runtime_data_uses_safe_empty_states(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.stack.count() == 8
    assert len(window.findChildren(EmptyState)) == 5
    assert window.mapping_page is None
    assert window.capture_page is None
    assert window.training_page is None
    assert window.settings_page is None

    labels = [label.text().casefold() for label in window.findChildren(QLabel)]
    assert not any("placeholder" in text for text in labels)


def test_main_window_uses_frameless_native_flags(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    flags = window.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowMinimizeButtonHint
    assert flags & Qt.WindowType.WindowMaximizeButtonHint


def test_main_window_sets_brand_icon(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert not window.windowIcon().isNull()


def test_main_window_tracks_taskbar_minimize_state(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    window.setWindowState(Qt.WindowState.WindowMinimized)
    window.changeEvent(QEvent(QEvent.Type.WindowStateChange))

    assert window._user_minimized is True

    window.setWindowState(Qt.WindowState.WindowNoState)
    window.changeEvent(QEvent(QEvent.Type.WindowStateChange))

    assert window._user_minimized is False


def test_main_window_uses_history_page_when_service_is_ready(tmp_path: Path, qtbot):
    history = HistoryService(tmp_path / "history.db")
    window = MainWindow(history=history)
    qtbot.addWidget(window)

    assert window.history_page is not None
    assert len(window.findChildren(EmptyState)) == 4
    history.close()


def test_main_window_exposes_manual_training_sidebar_when_config_ready(qtbot):
    window = MainWindow(cfg=AppConfig())
    qtbot.addWidget(window)

    assert "Huấn luyện" in NAV_ITEMS
    assert "Kiểm thử" in NAV_ITEMS
    assert window.stack.count() == len(NAV_ITEMS)
    assert window.capture_page is None
    assert window.training_page is None

    window.show_page(4)
    window.show_page(5)

    assert isinstance(window.capture_page, CapturePage)
    assert isinstance(window.training_page, TrainingPage)
    assert type(window.capture_page) is not type(window.training_page)


def test_training_sidebar_button_opens_manual_training_page(qtbot):
    window = MainWindow(cfg=AppConfig())
    qtbot.addWidget(window)

    window.sidebar._buttons[5].click()

    assert window.stack.currentIndex() == 5
    assert isinstance(window.training_page, TrainingPage)
    assert window.sidebar._buttons[5].isChecked() is True


def test_main_window_keeps_sidebar_active_when_stack_changes(qtbot):
    window = MainWindow(cfg=AppConfig())
    qtbot.addWidget(window)

    window.stack.setCurrentIndex(4)

    assert window.sidebar._buttons[4].isChecked() is True

    window.show_page(1)

    assert window.stack.currentIndex() == 1
    assert window.sidebar._buttons[1].isChecked() is True


def test_main_window_lazily_loads_data_and_training_pages(monkeypatch, qtbot):
    calls: list[str] = []

    def fake_capture_reload(self):
        self._loaded = True
        calls.append("data")

    def fake_training_reload(self):
        self._loaded = True
        calls.append("training")

    monkeypatch.setattr(CapturePage, "reload", fake_capture_reload)
    monkeypatch.setattr(TrainingPage, "reload", fake_training_reload)
    monkeypatch.setattr("app.ui.main_window._auto_heavy_page_load_enabled", lambda: True)

    window = MainWindow(cfg=AppConfig())
    qtbot.addWidget(window)

    assert calls == []
    assert window.capture_page is None
    assert window.training_page is None

    window.stack.setCurrentIndex(4)
    assert calls == ["data"]
    assert isinstance(window.capture_page, CapturePage)

    window.stack.setCurrentIndex(5)
    assert calls == ["data", "training"]
    assert isinstance(window.training_page, TrainingPage)


def test_main_window_emits_page_created_for_lazy_operational_pages(qtbot):
    window = MainWindow(cfg=AppConfig())
    qtbot.addWidget(window)
    created: list[tuple[int, object]] = []
    window.page_created.connect(lambda index, page: created.append((index, page)))

    window.show_page(3)
    window.show_page(4)
    window.show_page(5)
    window.show_page(7)

    assert [index for index, _page in created] == [3, 4, 5, 7]
    assert window.mapping_page is created[0][1]
    assert window.capture_page is created[1][1]
    assert window.training_page is created[2][1]
    assert window.settings_page is created[3][1]


def test_sidebar_icons_are_visible_on_dark_theme(qtbot):
    window = MainWindow(cfg=AppConfig())
    qtbot.addWidget(window)

    for button in window.sidebar.findChildren(QPushButton):
        pixmap = button.icon().pixmap(20, 20, QIcon.Mode.Normal, QIcon.State.Off)
        image = pixmap.toImage()
        visible_pixels = 0
        for x in range(image.width()):
            for y in range(image.height()):
                color = image.pixelColor(x, y)
                if color.alpha() > 0 and color.lightness() > 120:
                    visible_pixels += 1

        assert visible_pixels > 8, button.text()


def test_main_window_compacts_shell_on_laptop_width(qtbot):
    window = MainWindow(cfg=AppConfig())
    qtbot.addWidget(window)

    window.resize(900, 700)
    window._sync_responsive_shell()

    assert window.sidebar.width() == 76
    assert window.title_bar.btn_web.text() == ""
    assert window.title_bar.btn_camera.text() == ""

    window.resize(1280, 760)
    window._sync_responsive_shell()

    assert window.sidebar.width() == 240
    assert window.title_bar.btn_web.text() == "Mở Web"
    assert window.title_bar.btn_camera.text() == "Bật camera"


def test_live_detection_stream_does_not_expand_desktop_shell(qtbot):
    window = MainWindow(cfg=AppConfig())
    qtbot.addWidget(window)
    window.resize(900, 700)
    window.show()
    qtbot.waitExposed(window)

    detail = (
        "TEST OFF; inorganic; bin 2; payload voco; ACK only one object is allowed "
        "inside the tray, and this deliberately long message must not widen the shell."
    )
    for _ in range(12):
        window.live_page.append_detection("Pen", 0.65, "09:17:09", detail)

    assert window.live_page.stream.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert (
        window.live_page.stream.sizeAdjustPolicy()
        == QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored
    )
    assert window.live_page.stream.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    assert window.title_bar.btn_close.geometry().right() <= window.title_bar.width()


def test_main_window_clamps_restored_window_to_available_screen(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    screen = QGuiApplication.primaryScreen()
    assert screen is not None
    available = screen.availableGeometry()

    window.resize(available.width() + 500, available.height() + 500)
    window.move(available.right() + 200, available.bottom() + 200)
    window.ensure_visible_on_screen()
    frame = window.frameGeometry()

    assert frame.width() <= available.width()
    assert frame.height() <= available.height()
    assert frame.left() >= available.left()
    assert frame.top() >= available.top()
