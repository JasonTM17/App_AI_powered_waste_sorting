"""Mapping tab: edit class -> uart command rows, drag-reorder priority."""

from __future__ import annotations

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

# Visual category by class name keyword → dot color (waste taxonomy)
_CATEGORY_RULES = (
    # organic / food → green
    ("#10B981", ("food", "organic", "fruit", "vegetable", "leaf", "grass", "compost")),
    # paper / cardboard → amber
    ("#F59E0B", ("paper", "cardboard", "cellulose", "papier", "newspaper")),
    # plastic / glass / metal recyclable → blue
    ("#3B82F6", ("plastic", "bottle", "can", "glass", "metal", "aluminum", "tin", "polypropylene", "polyethylene", "tetra")),
    # hazardous → red
    ("#EF4444", ("battery", "electronic", "chemical", "medical", "syringe", "lamp", "bulb")),
    # textile / wood → violet
    ("#A855F7", ("textile", "fabric", "cloth", "wood", "leather", "shoe")),
)
_DEFAULT_DOT = "#64748B"  # slate — anything we can't categorise


def _category_color(class_name: str) -> str:
    n = class_name.lower()
    for color, kws in _CATEGORY_RULES:
        if any(k in n for k in kws):
            return color
    return _DEFAULT_DOT


class MappingRow(QWidget):
    test_clicked = Signal(str)
    changed = Signal()

    def __init__(self, mapping: ClassMapping, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        handle = QLabel("●")
        handle.setStyleSheet(
            f"color: {_category_color(mapping.class_name)}; font-size: 18px;"
            " min-width: 18px;"
        )
        layout.addWidget(handle)

        self.cls_label = QLabel(mapping.class_name)
        self.cls_label.setMinimumWidth(120)
        self.cls_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.cls_label)

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
        self.bin_spin.setFixedWidth(60)
        self.bin_spin.valueChanged.connect(self.changed.emit)
        layout.addWidget(self.bin_spin)

        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(mapping.enabled)
        self.enabled_check.toggled.connect(self.changed.emit)
        layout.addWidget(self.enabled_check)

        layout.addStretch()

        self.btn_test = QPushButton("▶ Test")
        self.btn_test.setObjectName("secondary")
        self.btn_test.clicked.connect(lambda: self.test_clicked.emit(self.cmd_edit.text() or "?"))
        layout.addWidget(self.btn_test)

    def _on_cmd_changed(self, text: str) -> None:
        upper = text.upper()
        if upper != text:
            self.cmd_edit.blockSignals(True)
            self.cmd_edit.setText(upper)
            self.cmd_edit.blockSignals(False)
        self.changed.emit()

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
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Mapping Class → Lệnh UART")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        header.addWidget(title)
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

        # protocol preview
        preview_card = QFrame()
        preview_card.setObjectName("card")
        prev_layout = QVBoxLayout(preview_card)
        prev_layout.setContentsMargins(20, 16, 20, 16)
        prev_title = QLabel("Protocol preview")
        prev_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #94A3B8;")
        prev_layout.addWidget(prev_title)
        self.preview_label = QLabel("—")
        self.preview_label.setStyleSheet(
            "font-family: 'JetBrains Mono', monospace; color: #10B981; padding: 8px; "
            "background: #0B1220; border-radius: 6px;"
        )
        prev_layout.addWidget(self.preview_label)
        outer.addWidget(preview_card)

        outer.addStretch()
        self._populate()

    def _populate(self) -> None:
        self.list_widget.clear()
        for m in self._mappings:
            row = MappingRow(m)
            row.test_clicked.connect(self.test_command_requested.emit)
            row.changed.connect(self._update_preview)
            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(row.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)
        self._update_preview()

    def _rows(self) -> list[MappingRow]:
        out = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            w = self.list_widget.itemWidget(item)
            if isinstance(w, MappingRow):
                out.append(w)
        return out

    def _update_preview(self) -> None:
        rows = self._rows()
        if not rows:
            self.preview_label.setText("—")
            return
        first = rows[0].to_mapping()
        try:
            payload = encode_sort(first.command, 0.92)
            self.preview_label.setText(payload.decode("utf-8").rstrip("\n") + "\\n")
        except Exception:
            self.preview_label.setText("invalid")

    def collect(self) -> list[ClassMapping]:
        return [r.to_mapping() for r in self._rows()]

    def _save(self) -> None:
        self.mappings_saved.emit(self.collect())

    def _reset(self) -> None:
        self._populate()
