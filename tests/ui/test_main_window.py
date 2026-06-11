import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QLabel, QPushButton

from app.core.config import AppConfig
from app.core.history import HistoryService
from app.ui.main_window import NAV_ITEMS, MainWindow
from app.ui.pages.capture import CapturePage
from app.ui.pages.training import TrainingPage
from app.ui.widgets.empty_state import EmptyState


def test_main_window_no_runtime_data_uses_safe_empty_states(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.stack.count() == 7
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
    assert window.stack.count() == len(NAV_ITEMS)
    assert window.capture_page is not None
    assert window.training_page is not None
    assert isinstance(window.capture_page, CapturePage)
    assert isinstance(window.training_page, TrainingPage)
    assert type(window.capture_page) is not type(window.training_page)


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

    window = MainWindow(cfg=AppConfig())
    qtbot.addWidget(window)

    assert calls == []

    window.stack.setCurrentIndex(3)
    assert calls == ["data"]

    window.stack.setCurrentIndex(4)
    assert calls == ["data", "training"]


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
