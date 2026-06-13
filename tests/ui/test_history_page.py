import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import UTC, datetime

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

from app.core.history import HistoryRow, HistoryService
from app.ui.pages.history import (
    HISTORY_FILTER_HEIGHT,
    HistoryPage,
    _chart_palette,
    _count_rows_by_class,
    _count_rows_by_hour,
)
from app.ui.widgets.safe_inputs import SafeComboBox, SafeDateEdit
from app.ui.widgets.theme import apply_theme


def test_history_chart_counts_use_filtered_rows_only():
    rows = [
        HistoryRow(cls_name="Paper", ts="2026-06-10T08:15:00+00:00"),
        HistoryRow(cls_name="Paper", ts="2026-06-10T08:45:00+00:00"),
        HistoryRow(cls_name="Plastic cup", ts="2026-06-10T14:00:00+00:00"),
    ]

    assert _count_rows_by_class(rows) == {"Paper": 2, "Plastic cup": 1}
    hourly = _count_rows_by_hour(rows)
    assert hourly[8] == 2
    assert hourly[14] == 1
    assert sum(hourly.values()) == 3


def test_history_chart_counts_stay_empty_when_filter_has_no_rows():
    assert _count_rows_by_class([]) == {}
    assert sum(_count_rows_by_hour([]).values()) == 0


def test_history_page_filters_charts_and_table_to_selected_date(tmp_path, qtbot):
    svc = HistoryService(tmp_path / "history.db")
    svc.insert(
        track_id=1,
        ts=datetime(2026, 6, 5, 9, 0, tzinfo=UTC),
        cls_id=1,
        cls_name="Aluminum can",
        conf=0.58,
        bbox=(0, 0, 10, 10),
        thumbnail=b"",
        uart_command="I",
        ack_status="ok",
    )
    page = HistoryPage(svc)
    qtbot.addWidget(page)

    page.date_from.setDate(QDate(2026, 6, 10))
    page.date_to.setDate(QDate(2026, 6, 10))
    page.reload()

    assert page.model.rowCount() == 0
    assert page.empty_label.isVisibleTo(page) is True
    assert page._bar_signature == ()
    assert page._area_signature == tuple(0 for _ in range(24))
    svc.close()


def test_history_page_uses_safe_even_filter_controls(tmp_path, qtbot):
    svc = HistoryService(tmp_path / "history.db")
    page = HistoryPage(svc)
    qtbot.addWidget(page)

    controls = (
        page.date_from,
        page.date_to,
        page.cls_filter,
        page.ack_filter,
        page.btn_refresh,
        page.btn_export,
    )

    assert isinstance(page.date_from, SafeDateEdit)
    assert isinstance(page.date_to, SafeDateEdit)
    assert isinstance(page.cls_filter, SafeComboBox)
    assert isinstance(page.ack_filter, SafeComboBox)
    assert all(control.minimumHeight() == HISTORY_FILTER_HEIGHT for control in controls)
    assert all(control.maximumHeight() == HISTORY_FILTER_HEIGHT for control in controls)
    svc.close()


def test_history_chart_palette_tracks_light_theme(tmp_path, qtbot):
    app = QApplication.instance()
    assert app is not None
    apply_theme(app, "light")
    svc = HistoryService(tmp_path / "history.db")
    try:
        page = HistoryPage(svc)
        qtbot.addWidget(page)

        assert _chart_palette()["plot_bg"] == "#F8FAFC"
    finally:
        apply_theme(app, "dark")
        svc.close()
