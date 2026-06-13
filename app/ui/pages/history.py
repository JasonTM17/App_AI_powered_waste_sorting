"""History tab: filter, charts, virtualized table."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import ClassVar

import pyqtgraph as pg
from PySide6.QtCore import QAbstractTableModel, QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
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
from app.ui.widgets.flow_layout import FlowLayout
from app.ui.widgets.safe_inputs import SafeComboBox, SafeDateEdit

pg.setConfigOption("background", "#060E20")
pg.setConfigOption("foreground", "#BBCABF")

MAX_BAR_CLASSES = 6
BAR_AXIS_LABEL_CHARS = 12
HISTORY_FILTER_HEIGHT = 40


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


class RecognitionTestTableModel(QAbstractTableModel):
    HEADERS: ClassVar[tuple[str, ...]] = (
        "Time",
        "Mẫu",
        "Lượt",
        "Nhãn thật",
        "AI dự đoán",
        "Kết luận",
        "Route",
        "ACK / RTT",
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
        row = self._rows[index.row()]
        values = (
            str(getattr(row, "completed_at", "")).replace("T", " ")[:19],
            getattr(row, "sample_label", ""),
            str(getattr(row, "trial_number", "")),
            getattr(row, "expected_class", ""),
            getattr(row, "predicted_class", "") or "không nhận diện",
            getattr(row, "verdict", ""),
            (
                f"{getattr(row, 'expected_route', '')} → "
                f"{getattr(row, 'predicted_route', '') or '-'}"
            ),
            (
                f"{getattr(row, 'ack_status', '') or '-'} / "
                f"{getattr(row, 'rtt_ms', '') or '-'} ms"
            ),
        )
        return values[index.column()]


def _section_card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    return f


def _filter_group(label_text: str, control: QWidget) -> QWidget:
    group = QWidget()
    layout = QHBoxLayout(group)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    label = QLabel(label_text)
    layout.addWidget(label)
    layout.addWidget(control)
    return group


class HistoryPage(QWidget):
    refresh_requested = Signal()
    qa_promote_requested = Signal(str)

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

        filter_card = QFrame()
        filter_card.setObjectName("toolbar")
        filter_layout = FlowLayout(filter_card, margin=0, h_spacing=12, v_spacing=8)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        self.date_from = SafeDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd/MM/yyyy")
        self.date_from.setDate(_recent_start_qdate())
        self.date_to = SafeDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd/MM/yyyy")
        self.date_to.setDate(_today_qdate())
        self.cls_filter = SafeComboBox()
        self.cls_filter.addItem("Tất cả lớp", "")
        self.ack_filter = SafeComboBox()
        self.ack_filter.addItems(["Tất cả", "ok", "no_ack", "error", "pending"])
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("secondary")
        self.btn_refresh.clicked.connect(lambda: self.request_reload())
        self.btn_export = QPushButton("Export CSV")
        self.btn_export.setObjectName("secondary")
        self.btn_export.clicked.connect(self._export)
        self.refresh_status = QLabel("Đang cập nhật...")
        self.refresh_status.setObjectName("muted")
        self.refresh_status.setVisible(False)
        for widget, width in (
            (self.date_from, 160),
            (self.date_to, 160),
            (self.cls_filter, 260),
            (self.ack_filter, 150),
            (self.btn_refresh, 112),
            (self.btn_export, 128),
        ):
            widget.setFixedHeight(HISTORY_FILTER_HEIGHT)
            widget.setMinimumWidth(width)
        filter_layout.addWidget(_filter_group("Từ ngày", self.date_from))
        filter_layout.addWidget(_filter_group("Đến ngày", self.date_to))
        filter_layout.addWidget(_filter_group("Lớp", self.cls_filter))
        filter_layout.addWidget(_filter_group("ACK", self.ack_filter))
        filter_layout.addWidget(self.btn_refresh)
        filter_layout.addWidget(self.btn_export)
        filter_layout.addWidget(self.refresh_status)
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
        bar_layout.addWidget(self.bar_plot)
        charts.addWidget(bar_card, 1)

        area_card = _section_card()
        area_layout = QVBoxLayout(area_card)
        area_layout.setContentsMargins(16, 16, 16, 16)
        area_layout.addWidget(QLabel("Theo giờ trong ngày (hôm nay)"))
        self.area_plot = pg.PlotWidget()
        self.area_plot.setMinimumHeight(220)
        area_layout.addWidget(self.area_plot)
        charts.addWidget(area_card, 1)
        self._apply_chart_theme()

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

        qa_card = _section_card()
        qa_layout = QVBoxLayout(qa_card)
        qa_layout.setContentsMargins(8, 8, 8, 8)
        qa_header = QHBoxLayout()
        qa_title = QLabel("PHIÊN TEST RÁC THẬT")
        qa_title.setObjectName("mono")
        self.qa_session_filter = SafeComboBox()
        self.qa_session_filter.setMinimumWidth(300)
        self.qa_session_filter.currentIndexChanged.connect(self._reload_qa_trials)
        self.btn_qa_export = QPushButton("Export QA")
        self.btn_qa_export.setObjectName("secondary")
        self.btn_qa_export.clicked.connect(self._export_qa)
        qa_header.addWidget(qa_title)
        qa_header.addStretch()
        qa_header.addWidget(QLabel("Phiên test"))
        qa_header.addWidget(self.qa_session_filter)
        qa_header.addWidget(self.btn_qa_export)
        qa_layout.addLayout(qa_header)
        self.qa_empty_label = QLabel("Chưa có lượt kiểm thử rác thật.")
        self.qa_empty_label.setObjectName("muted")
        self.qa_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qa_layout.addWidget(self.qa_empty_label)
        self.qa_table = QTableView()
        self.qa_model = RecognitionTestTableModel([])
        self.qa_table.setModel(self.qa_model)
        self.qa_table.setAlternatingRowColors(True)
        self.qa_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.qa_table.verticalHeader().setVisible(False)
        self.qa_table.doubleClicked.connect(self._open_qa_detail)
        qa_layout.addWidget(self.qa_table)
        outer.addWidget(qa_card, 1)

        QTimer.singleShot(0, self.request_reload)

    def changeEvent(self, event):  # noqa: N802
        super().changeEvent(event)
        if event.type() not in {
            QEvent.Type.StyleChange,
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
        }:
            return
        if not hasattr(self, "bar_plot"):
            return
        self._apply_chart_theme()
        self._bar_signature = None
        self._area_signature = None
        self.request_reload()

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
            self._refresh_qa_sessions()
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
        colors = _chart_palette()
        bg = pg.BarGraphItem(x=x, height=ys, width=0.6, brush=colors["bar"])
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
        colors = _chart_palette()
        curve = self.area_plot.plot(
            xs,
            ys,
            pen=pg.mkPen(colors["line"], width=2),
            fillLevel=0,
            brush=colors["area_fill"],
        )
        _ = curve

    def _apply_chart_theme(self) -> None:
        colors = _chart_palette()
        for plot, show_x_grid in ((self.bar_plot, False), (self.area_plot, True)):
            plot.setBackground(colors["plot_bg"])
            plot.showGrid(x=show_x_grid, y=True, alpha=colors["grid_alpha"])
            for axis_name in ("left", "bottom"):
                axis = plot.getAxis(axis_name)
                axis.setPen(pg.mkPen(colors["axis"]))
                axis.setTextPen(pg.mkPen(colors["text"]))

    def _open_detail(self, index) -> None:
        from app.ui.widgets.detail_dialog import DetectionDetailDialog

        if not index.isValid():
            return
        row = self.model._rows[index.row()] if 0 <= index.row() < len(self.model._rows) else None
        if row is None:
            return
        dlg = DetectionDetailDialog(row, self)
        dlg.exec()

    def _refresh_qa_sessions(self) -> None:
        sessions = self.history.list_qa_sessions()
        current = self.qa_session_filter.currentData() or ""
        self.qa_session_filter.blockSignals(True)
        self.qa_session_filter.clear()
        self.qa_session_filter.addItem("Tất cả phiên test", "")
        for session in sessions:
            label = (
                f"{str(getattr(session, 'started_at', '')).replace('T', ' ')[:19]} "
                f"| {getattr(session, 'phase', '')} | {getattr(session, 'status', '')}"
            )
            self.qa_session_filter.addItem(label, getattr(session, "id", ""))
        index = self.qa_session_filter.findData(current)
        if index >= 0:
            self.qa_session_filter.setCurrentIndex(index)
        self.qa_session_filter.blockSignals(False)
        self._reload_qa_trials()

    def _reload_qa_trials(self) -> None:
        session_id = self.qa_session_filter.currentData() or None
        rows = self.history.query_qa_trials(session_id=session_id, limit=500)
        self.qa_model.set_rows(rows)
        self.qa_empty_label.setVisible(not rows)

    def _open_qa_detail(self, index) -> None:
        from app.ui.widgets.detail_dialog import RecognitionTestDetailDialog

        if not index.isValid():
            return
        row = (
            self.qa_model._rows[index.row()]
            if 0 <= index.row() < len(self.qa_model._rows)
            else None
        )
        if row is None:
            return
        dialog = RecognitionTestDetailDialog(
            row,
            on_promote=self.qa_promote_requested.emit,
            parent=self,
        )
        dialog.exec()

    def refresh_qa(self) -> None:
        self._refresh_qa_sessions()

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "history.csv", "CSV (*.csv)")
        if not path:
            return
        self.history.export_csv(Path(path))

    def _export_qa(self) -> None:
        session_id = str(self.qa_session_filter.currentData() or "")
        if not session_id:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export QA",
            f"qa-{session_id[:8]}.csv",
            "CSV (*.csv);;JSON (*.json)",
        )
        if path:
            self.history.export_qa_session(session_id, Path(path))


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


def _chart_palette() -> dict[str, object]:
    app = QApplication.instance()
    theme = app.property("trashSorterTheme") if app is not None else "dark"
    if str(theme).strip().lower() == "light":
        return {
            "plot_bg": "#F8FAFC",
            "axis": "#94A3B8",
            "text": "#334155",
            "grid_alpha": 0.20,
            "bar": "#10B981",
            "line": "#0891B2",
            "area_fill": (8, 145, 178, 42),
        }
    return {
        "plot_bg": "#060E20",
        "axis": "#BBCABF",
        "text": "#DAE2FD",
        "grid_alpha": 0.12,
        "bar": "#4EDEA3",
        "line": "#4CD7F6",
        "area_fill": (3, 181, 211, 45),
    }
