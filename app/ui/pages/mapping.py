"""Mapping tab: edit class -> UART command rows and route details."""

from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.config import ClassMapping
from app.core.uart_protocol import encode_sort
from app.core.waste_categories import (
    CATEGORIES_BY_COMMAND,
    WasteCategory,
    category_for_bin_index,
    category_for_class,
    category_for_command,
)

_DEFAULT_DOT = "#64748B"


def _category_color(class_name: str) -> str:
    category = category_for_class(class_name)
    return {
        "O": "#10B981",
        "R": "#A855F7",
        "I": "#3B82F6",
    }.get(category.code, _DEFAULT_DOT)


def _route_for(mapping: ClassMapping) -> WasteCategory:
    return (
        category_for_command(mapping.command)
        or category_for_bin_index(mapping.bin_index)
        or category_for_class(mapping.class_name)
    )


def _vietnamese_name(class_name: str) -> str:
    vi_map = {
        "Organic": "Rác hữu cơ",
        "Aluminum can": "Lon nhôm",
        "Plastic bottle": "Chai nhựa PET",
        "Cardboard": "Thùng carton",
        "Paper": "Giấy",
        "Plastic bag": "Túi nylon",
        "Plastic cup": "Ly nhựa",
        "Tin": "Hộp thiếc",
        "Glass bottle": "Chai thủy tinh",
        "Pen": "Bút bi",
        "Battery": "Pin",
        "Toothbrush": "Bàn chải",
        "Textile": "Vải/Quần áo",
        "Disposable tableware": "Hộp xốp/1 lần",
        "Unknown plastic": "Nhựa khác",
        "Tetra pack": "Vỏ hộp sữa",
        "Ceramic": "Gốm sứ",
        "Aerosols": "Bình xịt",
        "Electronics": "Đồ điện tử",
        "Plastic caps": "Nắp nhựa",
        "Stretch film": "Màng bọc TP",
        "Paper cups": "Ly giấy",
        "Aluminum caps": "Nắp nhôm",
        "Foil": "Giấy bạc",
        "Postal packaging": "Bao bì CPN",
        "Scrap metal": "Sắt vụn",
        "Plastic canister": "Can/Hộp nhựa",
        "Paper bag": "Túi giấy",
    }
    return vi_map.get(class_name, "")


def _payload_preview(command: str) -> str:
    command = (command or "?").strip().upper()[:1] or "?"
    try:
        plain = encode_sort(command, 0.92, protocol="plain_group").decode("utf-8").strip()
    except ValueError:
        plain = "không hợp lệ"
    try:
        firmware = encode_sort(command, 0.92, protocol="sort_line").decode("utf-8").strip()
    except ValueError:
        firmware = "không hợp lệ"
    return f"{plain} | {firmware}"


def _status_for(mapping: ClassMapping) -> str:
    if not mapping.enabled:
        return "Đang tắt"
    category = category_for_command(mapping.command)
    if category is None:
        return "⚠️ Cần sửa Cmd"
    expected_category = category_for_class(mapping.class_name)
    if expected_category and expected_category.code != "other" and category.code != expected_category.code:
        return f"⚠️ Sai phân loại ({expected_category.code})"
    if int(mapping.bin_index) != int(category.bin_index):
        return f"⚠️ Lệch bin (nên là {category.bin_index})"
    return "✅ Sẵn sàng"


class MappingRow(QWidget):
    test_clicked = Signal(str)
    changed = Signal()

    def __init__(self, mapping: ClassMapping, parent=None):
        super().__init__(parent)
        self.setObjectName("mapping-row")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(10)

        handle = QLabel("*")
        handle.setStyleSheet(
            f"color: {_category_color(mapping.class_name)}; font-size: 18px; min-width: 18px;"
        )
        layout.addWidget(handle)

        self.cls_label = QLabel(mapping.class_name)
        self.cls_label.setMinimumWidth(130)
        self.cls_label.setStyleSheet("font-weight: 700; color: #DAE2FD;")
        layout.addWidget(self.cls_label)

        self.vi_label = QLabel(_vietnamese_name(mapping.class_name))
        self.vi_label.setMinimumWidth(110)
        self.vi_label.setStyleSheet("color: #94A3B8; font-size: 13px;")
        layout.addWidget(self.vi_label)

        self.route_label = QLabel("")
        self.route_label.setMinimumWidth(130)
        self.route_label.setObjectName("muted")
        layout.addWidget(self.route_label)

        layout.addWidget(QLabel("Cmd"))
        self.cmd_edit = QLineEdit(mapping.command)
        self.cmd_edit.setMaxLength(1)
        self.cmd_edit.setFixedWidth(50)
        self.cmd_edit.textChanged.connect(self._on_cmd_changed)
        layout.addWidget(self.cmd_edit)

        layout.addWidget(QLabel("Bin"))
        self.bin_spin = QSpinBox()
        self.bin_spin.setRange(1, 9)
        self.bin_spin.setValue(mapping.bin_index)
        self.bin_spin.setFixedWidth(58)
        self.bin_spin.valueChanged.connect(self._on_bin_changed)
        layout.addWidget(self.bin_spin)

        self.payload_label = QLabel("")
        self.payload_label.setMinimumWidth(190)
        self.payload_label.setObjectName("mono")
        layout.addWidget(self.payload_label)

        self.status_label = QLabel("")
        self.status_label.setMinimumWidth(120)
        layout.addWidget(self.status_label)

        self.enabled_check = QCheckBox("Bật")
        self.enabled_check.setChecked(mapping.enabled)
        self.enabled_check.toggled.connect(self._on_enabled_changed)
        layout.addWidget(self.enabled_check)

        layout.addStretch()

        self.btn_test = QPushButton("Test")
        self.btn_test.setObjectName("secondary")
        self.btn_test.clicked.connect(lambda: self.test_clicked.emit(self.cmd_edit.text() or "?"))
        layout.addWidget(self.btn_test)
        self._refresh_details()

    def _on_cmd_changed(self, text: str) -> None:
        upper = text.upper()
        if upper != text:
            self.cmd_edit.blockSignals(True)
            self.cmd_edit.setText(upper)
            self.cmd_edit.blockSignals(False)
        self._refresh_details()
        self.changed.emit()

    def _on_bin_changed(self) -> None:
        self._refresh_details()
        self.changed.emit()

    def _on_enabled_changed(self) -> None:
        self._refresh_details()
        self.changed.emit()

    def _refresh_details(self) -> None:
        mapping = self.to_mapping()
        route = _route_for(mapping)
        self.route_label.setText(f"{route.name} (T.{route.bin_index})")
        self.payload_label.setText(_payload_preview(mapping.command))
        status = _status_for(mapping)
        self.status_label.setText(status)
        
        color = "#6FFBBE" if "✅" in status else "#FBBF24"
        if status == "Đang tắt":
            color = "#86948A"
        elif "⚠️" in status:
            color = "#F87171"
            
        self.status_label.setStyleSheet(f"color: {color}; font-weight: 700;")
        
        if "⚠️" in status:
            self.setStyleSheet("QWidget#mapping-row { background: rgba(248, 113, 113, 0.05); border: 1px solid rgba(248, 113, 113, 0.2); border-radius: 6px; }")
        else:
            self.setStyleSheet("QWidget#mapping-row { background: transparent; border: none; }")

    def to_mapping(self) -> ClassMapping:
        return ClassMapping(
            class_name=self.cls_label.text(),
            command=self.cmd_edit.text() or "X",
            bin_index=self.bin_spin.value(),
            enabled=self.enabled_check.isChecked(),
        )


class MappingPage(QWidget):
    mappings_saved = Signal(list)
    test_command_requested = Signal(str)

    def __init__(self, mappings: list[ClassMapping], parent=None):
        super().__init__(parent)
        self._mappings = list(mappings)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(16)

        header = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("h1")
        header.addWidget(self.title)
        header.addStretch()
        btn_reset = QPushButton("Reset")
        btn_reset.setObjectName("secondary")
        btn_reset.clicked.connect(self._reset)
        btn_save = QPushButton("Lưu")
        btn_save.setObjectName("primary")
        btn_save.clicked.connect(self._save)
        header.addWidget(btn_reset)
        header.addWidget(btn_save)
        outer.addLayout(header)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("muted")
        self.summary_label.setWordWrap(True)
        outer.addWidget(self.summary_label)

        list_card = QFrame()
        list_card.setObjectName("card")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(8, 8, 8, 8)
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list_widget.setStyleSheet("QListWidget { border: none; }")
        list_layout.addWidget(self.list_widget)
        outer.addWidget(list_card)

        preview_card = QFrame()
        preview_card.setObjectName("card")
        prev_layout = QVBoxLayout(preview_card)
        prev_layout.setContentsMargins(20, 16, 20, 16)
        prev_title = QLabel("Protocol preview: O=Hữu cơ, R=Vô cơ, I=Tái chế")
        prev_title.setObjectName("mono")
        prev_layout.addWidget(prev_title)
        self.preview_label = QLabel("-")
        self.preview_label.setStyleSheet(
            "font-family: 'Consolas'; color: #4EDEA3; padding: 10px; "
            "background: #060E20; border: 1px solid rgba(78,222,163,0.20); "
            "border-radius: 8px;"
        )
        prev_layout.addWidget(self.preview_label)
        outer.addWidget(preview_card)

        outer.addStretch()
        self._populate()

    def _populate(self) -> None:
        self.list_widget.clear()
        self.title.setText(f"Mapping {len(self._mappings)} lớp -> 3 thùng")
        for m in self._mappings:
            row = MappingRow(m)
            row.test_clicked.connect(self.test_command_requested.emit)
            row.changed.connect(self._on_row_changed)
            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(row.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)
        self._sync_summary()
        self._update_preview()

    def _rows(self) -> list[MappingRow]:
        out = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            w = self.list_widget.itemWidget(item)
            if isinstance(w, MappingRow):
                out.append(w)
        return out

    def _on_row_changed(self) -> None:
        self._sync_summary()
        self._update_preview()

    def _sync_summary(self) -> None:
        rows = [row.to_mapping() for row in self._rows()]
        route_counts = Counter()
        invalid = 0
        disabled = 0
        unmapped_or_wrong = 0
        for mapping in rows:
            if not mapping.enabled:
                disabled += 1
                unmapped_or_wrong += 1
                continue
            status = _status_for(mapping)
            if "⚠️" in status:
                unmapped_or_wrong += 1
                
            category = category_for_command(mapping.command)
            if category is None:
                invalid += 1
                continue
            route_counts[category.code] += 1
            
        enabled = len(rows) - disabled
        route_text = " | ".join(
            f"{cat.name}: {route_counts.get(code, 0)}"
            for code, cat in CATEGORIES_BY_COMMAND.items()
        )
        
        warning_text = ""
        if unmapped_or_wrong > 0:
            warning_text = f" <span style='color: #F87171; font-weight: bold;'>({unmapped_or_wrong} lỗi cần chú ý)</span>"
            
        self.summary_label.setText(
            f"Tổng: {len(rows)} class. Bật: {enabled}. Tắt: {disabled}.{warning_text}<br>"
            f"Phân tuyến 3 thùng: <b>{route_text}</b>"
        )

    def _update_preview(self) -> None:
        rows = self._rows()
        if not rows:
            self.preview_label.setText("-")
            return
        first = rows[0].to_mapping()
        lines = []
        try:
            block_payload = encode_sort(first.command, 0.92, protocol="plain_group")
            lines.append("Block: " + block_payload.decode("utf-8").rstrip("\n") + "\\n")
        except Exception:
            lines.append("Block: invalid\\n")
        try:
            firmware_payload = encode_sort(first.command, 0.92, protocol="sort_line")
            lines.append("Firmware: " + firmware_payload.decode("utf-8").rstrip("\n") + "\\n")
        except Exception:
            lines.append("Firmware: invalid\\n")
        self.preview_label.setText("".join(lines))

    def collect(self) -> list[ClassMapping]:
        return [r.to_mapping() for r in self._rows()]

    def _save(self) -> None:
        self.mappings_saved.emit(self.collect())

    def _reset(self) -> None:
        self._populate()
