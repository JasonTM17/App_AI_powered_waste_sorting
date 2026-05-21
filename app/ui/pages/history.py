"""History tab: filter, charts, virtualized table."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
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

pg.setConfigOption("background", "#111A2E")
pg.setConfigOption("foreground", "#94A3B8")


class HistoryTableModel(QAbstractTableModel):
    HEADERS = ["Time", "Class", "Conf", "Cmd", "Ack", "RTT (ms)"]

    def __init__(self, rows=None):
        super().__init__()
        self._rows = rows or []

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, _parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, _parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
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
            return f"{getattr(r, 'conf', 0):.2f}"
        if col == 3:
            return getattr(r, "uart_command", "") or ""
        if col == 4:
            return getattr(r, "ack_status", "") or ""
        if col == 5:
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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(16)

        title = QLabel("Lịch sử & Thống kê")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        outer.addWidget(title)

        # filter row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(12)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(_today_qdate())
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(_today_qdate())
        self.cls_filter = QComboBox()
        self.cls_filter.addItem("Tất cả lớp", "")
        self.ack_filter = QComboBox()
        self.ack_filter.addItems(["Tất cả", "ok", "no_ack", "error", "pending"])
        btn_refresh = QPushButton("↻ Refresh")
        btn_refresh.setObjectName("secondary")
        btn_refresh.clicked.connect(self.reload)
        btn_export = QPushButton("⤓ Export CSV")
        btn_export.setObjectName("secondary")
        btn_export.clicked.connect(self._export)
        filter_row.addWidget(QLabel("Từ ngày"))
        filter_row.addWidget(self.date_from)
        filter_row.addWidget(QLabel("Đến ngày"))
        filter_row.addWidget(self.date_to)
        filter_row.addWidget(self.cls_filter)
        filter_row.addWidget(self.ack_filter)
        filter_row.addStretch()
        filter_row.addWidget(btn_refresh)
        filter_row.addWidget(btn_export)
        outer.addLayout(filter_row)

        # charts row
        charts = QHBoxLayout()
        charts.setSpacing(16)

        bar_card = _section_card()
        bar_layout = QVBoxLayout(bar_card)
        bar_layout.setContentsMargins(16, 16, 16, 16)
        bar_layout.addWidget(QLabel("Phân bố theo lớp"))
        self.bar_plot = pg.PlotWidget()
        self.bar_plot.setMinimumHeight(220)
        self.bar_plot.showGrid(x=False, y=True, alpha=0.2)
        bar_layout.addWidget(self.bar_plot)
        charts.addWidget(bar_card, 1)

        area_card = _section_card()
        area_layout = QVBoxLayout(area_card)
        area_layout.setContentsMargins(16, 16, 16, 16)
        area_layout.addWidget(QLabel("Theo giờ trong ngày (hôm nay)"))
        self.area_plot = pg.PlotWidget()
        self.area_plot.setMinimumHeight(220)
        self.area_plot.showGrid(x=True, y=True, alpha=0.2)
        area_layout.addWidget(self.area_plot)
        charts.addWidget(area_card, 1)

        outer.addLayout(charts)

        # table
        table_card = _section_card()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(8, 8, 8, 8)
        self.table = QTableView()
        self.model = HistoryTableModel([])
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._open_detail)
        table_layout.addWidget(self.table)
        outer.addWidget(table_card, 1)

        self.reload()

    def reload(self) -> None:
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
        rows = self.history.query(limit=500, cls_name=cls, since=since_dt)
        rows = [
            r for r in rows
            if (ts := getattr(r, "ts", "")) and ts <= until_dt.isoformat()
        ]
        if ack and ack != "Tất cả":
            rows = [r for r in rows if getattr(r, "ack_status", None) == ack]
        self.model.set_rows(rows)
        self._refresh_class_filter(rows)
        self._draw_bar()
        self._draw_area()

    def _refresh_class_filter(self, rows) -> None:
        seen = set()
        for r in rows:
            n = getattr(r, "cls_name", "")
            if n:
                seen.add(n)
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

    def _draw_bar(self) -> None:
        counts = self.history.count_by_class()
        items = sorted(counts.items(), key=lambda kv: -kv[1])[:10]
        self.bar_plot.clear()
        if not items:
            return
        x = list(range(len(items)))
        ys = [v for _, v in items]
        bg = pg.BarGraphItem(x=x, height=ys, width=0.6, brush="#10B981")
        self.bar_plot.addItem(bg)
        ax = self.bar_plot.getAxis("bottom")
        ax.setTicks([list(zip(x, [k for k, _ in items]))])

    def _draw_area(self) -> None:
        today = datetime.now(timezone.utc)
        per_hour = self.history.count_by_hour(today)
        xs = list(range(24))
        ys = [per_hour.get(h, 0) for h in xs]
        self.area_plot.clear()
        curve = self.area_plot.plot(
            xs, ys, pen=pg.mkPen("#10B981", width=2), fillLevel=0, brush=(16, 185, 129, 60)
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


def _today_qdate():
    from PySide6.QtCore import QDate

    n = datetime.now()
    return QDate(n.year, n.month, n.day)
