"""History tab: filter, charts, virtualized table."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import ClassVar

import pyqtgraph as pg
from PySide6.QtCore import QAbstractTableModel, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.core.history import HistoryService

pg.setConfigOption("background", "#060E20")
pg.setConfigOption("foreground", "#BBCABF")

MAX_BAR_CLASSES = 6
BAR_AXIS_LABEL_CHARS = 12


class HistoryTableModel(QAbstractTableModel):
    HEADERS: ClassVar[tuple[str, ...]] = (
        "Time",
        "Class",
        "Nhóm",
        "Thùng",
        "Conf",
        "Cmd",
        "Ack",
        "RTT (ms)",
    )

    def __init__(self, rows=None):
        super().__init__()
        self._rows = rows or []

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, _parent=None):  # noqa: N802
        return len(self._rows)

    def columnCount(self, _parent=None):  # noqa: N802
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        r = self._rows[index.row()]
        col = index.column()
        if col == 0:
            ts = getattr(r, "ts", "")
            return ts.replace("T", " ")[:19]
        if col == 1:
            return getattr(r, "cls_name", "")
        if col == 2:
            return getattr(r, "route_label", "") or ""
        if col == 3:
            v = getattr(r, "bin_index", None)
            return str(v) if v is not None else ""
        if col == 4:
            return f"{getattr(r, 'conf', 0):.2f}"
        if col == 5:
            return getattr(r, "uart_command", "") or ""
        if col == 6:
            return getattr(r, "ack_status", "") or ""
        if col == 7:
            v = getattr(r, "rtt_ms", None)
            return str(v) if v is not None else ""
        return None


def _section_card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    return f


class HistoryPage(QWidget):
    refresh_requested = Signal()

    def __init__(self, history: HistoryService, parent=None):
        super().__init__(parent)
        self.history = history
        self._reload_in_progress = False
        self._reload_again = False
        self._bar_signature: tuple[tuple[str, int], ...] | None = None
        self._area_signature: tuple[int, ...] | None = None
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(150)
        self._reload_timer.timeout.connect(self.reload)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(16)

        title = QLabel("Lịch sử & Thống kê")
        title.setObjectName("h1")
        outer.addWidget(title)

        # filter row: 2-row grid so it wraps on narrow widths
        from PySide6.QtWidgets import QGridLayout

        filter_card = QFrame()
        filter_card.setObjectName("toolbar")
        filter_grid = QGridLayout(filter_card)
        filter_grid.setContentsMargins(16, 12, 16, 12)
        filter_grid.setHorizontalSpacing(12)
        filter_grid.setVerticalSpacing(8)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(_recent_start_qdate())
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(_today_qdate())
        self.cls_filter = QComboBox()
        self.cls_filter.addItem("Tất cả lớp", "")
        self.cls_filter.setMinimumWidth(160)
        self.ack_filter = QComboBox()
        self.ack_filter.addItems(["Tất cả", "ok", "no_ack", "error", "pending"])
        self.ack_filter.setMinimumWidth(120)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("secondary")
        self.btn_refresh.clicked.connect(lambda: self.request_reload())
        self.btn_export = QPushButton("Export CSV")
        self.btn_export.setObjectName("secondary")
        self.btn_export.clicked.connect(self._export)
        self.refresh_status = QLabel("Đang cập nhật...")
        self.refresh_status.setObjectName("muted")
        self.refresh_status.setVisible(False)
        filter_grid.addWidget(QLabel("Từ ngày"), 0, 0)
        filter_grid.addWidget(self.date_from, 0, 1)
        filter_grid.addWidget(QLabel("Đến ngày"), 0, 2)
        filter_grid.addWidget(self.date_to, 0, 3)
        filter_grid.addWidget(QLabel("Lớp"), 0, 4)
        filter_grid.addWidget(self.cls_filter, 0, 5)
        filter_grid.addWidget(QLabel("ACK"), 0, 6)
        filter_grid.addWidget(self.ack_filter, 0, 7)
        filter_grid.addWidget(self.btn_refresh, 0, 8)
        filter_grid.addWidget(self.btn_export, 0, 9)
        filter_grid.addWidget(self.refresh_status, 1, 0, 1, 10)
        filter_grid.setColumnStretch(10, 1)
        outer.addWidget(filter_card)
        self.date_from.dateChanged.connect(lambda *_args: self.request_reload())
        self.date_to.dateChanged.connect(lambda *_args: self.request_reload())
        self.cls_filter.currentIndexChanged.connect(lambda *_args: self.request_reload())
        self.ack_filter.currentIndexChanged.connect(lambda *_args: self.request_reload())

        # charts row
        charts = QHBoxLayout()
        charts.setSpacing(16)

        bar_card = _section_card()
        bar_layout = QVBoxLayout(bar_card)
        bar_layout.setContentsMargins(16, 16, 16, 16)
        bar_layout.addWidget(QLabel("Phân bố theo lớp"))
        self.bar_plot = pg.PlotWidget()
        self.bar_plot.setMinimumHeight(220)
        self.bar_plot.setBackground("#060E20")
        self.bar_plot.showGrid(x=False, y=True, alpha=0.12)
        bar_layout.addWidget(self.bar_plot)
        charts.addWidget(bar_card, 1)

        area_card = _section_card()
        area_layout = QVBoxLayout(area_card)
        area_layout.setContentsMargins(16, 16, 16, 16)
        area_layout.addWidget(QLabel("Theo giờ trong ngày (hôm nay)"))
        self.area_plot = pg.PlotWidget()
        self.area_plot.setMinimumHeight(220)
        self.area_plot.setBackground("#060E20")
        self.area_plot.showGrid(x=True, y=True, alpha=0.12)
        area_layout.addWidget(self.area_plot)
        charts.addWidget(area_card, 1)

        outer.addLayout(charts)

        # table
        table_card = _section_card()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(8, 8, 8, 8)
        self.empty_label = QLabel("Chưa có lịch sử nhận diện trong khoảng thời gian này.")
        self.empty_label.setObjectName("muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setMinimumHeight(42)
        table_layout.addWidget(self.empty_label)
        self.table = QTableView()
        self.model = HistoryTableModel([])
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._open_detail)
        table_layout.addWidget(self.table)
        outer.addWidget(table_card, 1)

        QTimer.singleShot(0, self.request_reload)

    def request_reload(self) -> None:
        """Debounce UI refresh requests from filters or image actions."""
        if self._reload_in_progress:
            self._reload_again = True
            return
        self._set_busy(True)
        self._reload_timer.start()

    def reload(self) -> None:
        if self._reload_in_progress:
            self._reload_again = True
            return
        self._reload_timer.stop()
        self._reload_in_progress = True
        self._set_busy(True)
        try:
            cls = self.cls_filter.currentData() or None
            ack = self.ack_filter.currentText()
            since_qdate = self.date_from.date().toPython()
            since_dt = datetime(
                since_qdate.year, since_qdate.month, since_qdate.day, tzinfo=timezone.utc
            )
            until_qdate = self.date_to.date().toPython()
            until_dt = datetime(
                until_qdate.year, until_qdate.month, until_qdate.day,
                23, 59, 59, tzinfo=timezone.utc,
            )
            ack_filter = ack if ack and ack != "Tất cả" else None
            rows = self.history.query(
                limit=500,
                cls_name=cls,
                since=since_dt,
                until=until_dt,
                ack_status=ack_filter,
            )
            filter_counts = self.history.count_by_class(
                since=since_dt,
                until=until_dt,
                ack_status=ack_filter,
            )
            class_counts = _count_rows_by_class(rows)
            hourly_counts = _count_rows_by_hour(rows)
            self.model.set_rows(rows)
            self.empty_label.setVisible(not rows)
            self._refresh_class_filter(filter_counts)
            self._draw_bar(class_counts)
            self._draw_area(hourly_counts)
        finally:
            self._reload_in_progress = False
            self._set_busy(False)
            if self._reload_again:
                self._reload_again = False
                self.request_reload()

    def _set_busy(self, busy: bool) -> None:
        self.btn_refresh.setEnabled(not busy)
        self.btn_export.setEnabled(not busy)
        self.refresh_status.setVisible(busy)

    def _refresh_class_filter(self, counts: dict[str, int]) -> None:
        seen = {name for name in counts if name}
        current = self.cls_filter.currentData() or ""
        self.cls_filter.blockSignals(True)
        self.cls_filter.clear()
        self.cls_filter.addItem("Tất cả lớp", "")
        for name in sorted(seen):
            self.cls_filter.addItem(name, name)
        idx = self.cls_filter.findData(current)
        if idx >= 0:
            self.cls_filter.setCurrentIndex(idx)
        self.cls_filter.blockSignals(False)

    def _draw_bar(self, counts: dict[str, int]) -> None:
        items = sorted(counts.items(), key=lambda kv: -kv[1])[:MAX_BAR_CLASSES]
        signature = tuple((str(k), int(v)) for k, v in items)
        if signature == self._bar_signature:
            return
        self._bar_signature = signature
        self.bar_plot.clear()
        if not items:
            return
        x = list(range(len(items)))
        ys = [v for _, v in items]
        bg = pg.BarGraphItem(x=x, height=ys, width=0.6, brush="#4EDEA3")
        self.bar_plot.addItem(bg)
        ax = self.bar_plot.getAxis("bottom")
        ax.setStyle(tickTextOffset=8, autoExpandTextSpace=False, tickTextHeight=40)
        ax.setTicks([list(zip(x, [_short_axis_label(k) for k, _ in items], strict=False))])
        self.bar_plot.setXRange(-0.75, len(items) - 0.25, padding=0)

    def _draw_area(self, per_hour: dict[int, int]) -> None:
        xs = list(range(24))
        ys = [per_hour.get(h, 0) for h in xs]
        signature = tuple(int(v) for v in ys)
        if signature == self._area_signature:
            return
        self._area_signature = signature
        self.area_plot.clear()
        curve = self.area_plot.plot(
            xs, ys, pen=pg.mkPen("#4CD7F6", width=2), fillLevel=0, brush=(3, 181, 211, 45)
        )
        _ = curve

    def _open_detail(self, index) -> None:
        from app.ui.widgets.detail_dialog import DetectionDetailDialog

        if not index.isValid():
            return
        row = self.model._rows[index.row()] if 0 <= index.row() < len(self.model._rows) else None
        if row is None:
            return
        dlg = DetectionDetailDialog(row, self)
        dlg.exec()

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "history.csv", "CSV (*.csv)")
        if not path:
            return
        n = self.history.export_csv(Path(path))
        print(f"exported {n} rows to {path}")


def _recent_start_qdate(days: int = 30):
    from PySide6.QtCore import QDate

    n = datetime.now() - timedelta(days=days)
    return QDate(n.year, n.month, n.day)


def _today_qdate():
    from PySide6.QtCore import QDate

    n = datetime.now()
    return QDate(n.year, n.month, n.day)


def _count_rows_by_class(rows) -> dict[str, int]:
    names = (
        str(getattr(row, "cls_name", "") or "")
        for row in rows
        if getattr(row, "cls_name", "")
    )
    return dict(Counter(names))


def _count_rows_by_hour(rows) -> dict[int, int]:
    out: dict[int, int] = {h: 0 for h in range(24)}
    for row in rows:
        raw = str(getattr(row, "ts", "") or "")
        try:
            hour = datetime.fromisoformat(raw).hour
        except ValueError:
            try:
                hour = int(raw[11:13])
            except (ValueError, IndexError):
                continue
        out[hour] = out.get(hour, 0) + 1
    return out


def _short_axis_label(label: str) -> str:
    clean = " ".join(str(label).split())
    if len(clean) <= BAR_AXIS_LABEL_CHARS:
        return clean
    return clean[: BAR_AXIS_LABEL_CHARS - 3].rstrip() + "..."
