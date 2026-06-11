"""Theme-aware SVG icon rendering for Qt widgets."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_HEX_COLOR_RE = re.compile(r'(stroke|fill)="#[0-9A-Fa-f]{3,8}"')


def sidebar_icon(svg_path: Path, *, theme: str, size: int = 22) -> QIcon:
    palette = _sidebar_palette(theme)
    icon = QIcon()
    icon.addPixmap(_render(svg_path, palette["normal"], size), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_render(svg_path, palette["active"], size), QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(_render(svg_path, palette["checked"], size), QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(_render(svg_path, palette["disabled"], size), QIcon.Mode.Disabled, QIcon.State.Off)
    return icon


def _sidebar_palette(theme: str) -> dict[str, str]:
    if str(theme).strip().lower() == "light":
        return {
            "normal": "#334155",
            "active": "#0F172A",
            "checked": "#047857",
            "disabled": "#94A3B8",
        }
    return {
        "normal": "#DCE7E0",
        "active": "#F2F6FF",
        "checked": "#6FFBBE",
        "disabled": "#87929B",
    }


def _render(svg_path: Path, color: str, size: int) -> QPixmap:
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    if not svg_path.exists():
        return pixmap

    data = svg_path.read_text(encoding="utf-8")
    data = data.replace("currentColor", color)
    data = _HEX_COLOR_RE.sub(lambda match: f'{match.group(1)}="{color}"', data)
    renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()

    # Some SVGs may use path fills without explicit color. Treat the rendered
    # alpha mask as the source of truth and tint it consistently.
    if not renderer.isValid():
        mask = QPixmap(QSize(size, size))
        mask.fill(QColor(color))
        return mask
    return pixmap
