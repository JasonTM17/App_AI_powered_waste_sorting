"""Sidebar with mutually-exclusive nav buttons."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.brand_assets import brand_mark_path
from app.ui.widgets.themed_icon import sidebar_icon
from app.utils.paths import resource_path


def _icon(name: str, theme: str) -> QIcon:
    p = resource_path(f"app/ui/resources/icons/{name}.svg")
    return sidebar_icon(p, theme=theme, size=22) if p.exists() else QIcon()


class Sidebar(QWidget):
    page_changed = Signal(int)

    def __init__(self, items, icons=None, parent=None, theme: str = "dark"):
        super().__init__(parent)
        self._theme = theme
        self._icon_names: list[str | None] = list(icons or [None] * len(items))
        self.setObjectName("sidebar")
        self.setFixedWidth(240)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 22, 16, 18)
        layout.setSpacing(8)

        brand = QWidget()
        brand_row = QHBoxLayout(brand)
        brand_row.setContentsMargins(0, 0, 0, 14)
        brand_row.setSpacing(10)
        logo = QLabel()
        logo_path = brand_mark_path()
        if logo_path.exists():
            logo.setPixmap(QIcon(str(logo_path)).pixmap(QSize(30, 30)))
        logo.setFixedSize(34, 34)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(logo)

        brand_text = QWidget()
        brand_text_layout = QVBoxLayout(brand_text)
        brand_text_layout.setContentsMargins(0, 0, 0, 0)
        brand_text_layout.setSpacing(0)
        brand_title = QLabel("Trash Sorter Pro")
        brand_title.setObjectName("sidebar-brand")
        brand_subtitle = QLabel("Cyber-Eco Control")
        brand_subtitle.setObjectName("sidebar-subtitle")
        brand_text_layout.addWidget(brand_title)
        brand_text_layout.addWidget(brand_subtitle)
        brand_row.addWidget(brand_text, 1)
        layout.addWidget(brand)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []

        for idx, (label, icon_name) in enumerate(zip(items, self._icon_names, strict=False)):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if icon_name:
                btn.setIcon(_icon(icon_name, self._theme))
                btn.setIconSize(QSize(20, 20))
            self._group.addButton(btn, idx)
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()
        if self._buttons:
            self._buttons[0].setChecked(True)
        self._group.idClicked.connect(self.page_changed.emit)

    def set_active(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        for button, icon_name in zip(self._buttons, self._icon_names, strict=False):
            if icon_name:
                button.setIcon(_icon(icon_name, self._theme))
