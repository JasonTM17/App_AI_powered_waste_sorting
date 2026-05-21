"""Detail dialog: thumbnail preview + detection metadata."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _info_row(label: str, value: str) -> tuple[QLabel, QLabel]:
    lab = QLabel(label.upper())
    lab.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600; letter-spacing: 1px;")
    val = QLabel(value)
    val.setStyleSheet("color: #F1F5F9; font-family: 'JetBrains Mono', monospace;")
    return lab, val


class DetectionDetailDialog(QDialog):
    def __init__(self, row, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Chi tiết detection")
        self.setMinimumSize(720, 480)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(20)

        # left: image
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setStyleSheet("background: #000; border-radius: 8px;")
        img_label.setMinimumSize(360, 360)
        thumb = getattr(row, "thumbnail", None) or b""
        if thumb:
            pix = QPixmap()
            pix.loadFromData(bytes(thumb))
            if not pix.isNull():
                img_label.setPixmap(
                    pix.scaled(
                        360, 360,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                img_label.setText("(no image)")
        else:
            img_label.setText("(no image)")
        outer.addWidget(img_label, 1)

        # right: info
        info = QVBoxLayout()
        info.setSpacing(10)

        title = QLabel("Detection")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        info.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(8)

        def _add(label, value):
            lab, val = _info_row(label, value)
            form.addRow(lab, val)

        _add("ID", str(getattr(row, "id", "—")))
        _add("Track ID", str(getattr(row, "track_id", "—")))
        _add("Time", str(getattr(row, "ts", "—")).replace("T", " ")[:19])
        _add("Class", f"{getattr(row, 'cls_name', '—')} (id={getattr(row, 'cls_id', '—')})")
        _add("Confidence", f"{getattr(row, 'conf', 0):.2f}")
        bx1 = getattr(row, "bbox_x1", None)
        by1 = getattr(row, "bbox_y1", None)
        bx2 = getattr(row, "bbox_x2", None)
        by2 = getattr(row, "bbox_y2", None)
        bbox_str = f"({bx1},{by1}) → ({bx2},{by2})" if None not in (bx1, by1, bx2, by2) else "—"
        _add("BBox", bbox_str)
        _add("UART cmd", getattr(row, "uart_command", "—") or "—")
        _add("Ack", getattr(row, "ack_status", "—") or "—")
        rtt = getattr(row, "rtt_ms", None)
        _add("RTT", f"{rtt} ms" if rtt is not None else "—")

        info.addLayout(form)
        info.addStretch()

        btn_close = QPushButton("Đóng")
        btn_close.setObjectName("primary")
        btn_close.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        info.addLayout(btn_row)

        outer.addLayout(info, 1)
