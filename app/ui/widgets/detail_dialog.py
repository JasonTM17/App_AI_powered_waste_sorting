"""Detail dialog: thumbnail preview + detection metadata."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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
    val.setStyleSheet("color: #DAE2FD; font-family: 'Consolas';")
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
        pix = QPixmap()
        annotated_path = Path(str(getattr(row, "annotated_path", "") or ""))
        if annotated_path.exists():
            pix.load(str(annotated_path))
        thumb = getattr(row, "thumbnail", None) or b""
        if pix.isNull() and thumb:
            pix.loadFromData(bytes(thumb))
        if not pix.isNull():
            img_label.setPixmap(
                pix.scaled(
                    360,
                    360,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
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
        _add("Nhóm", getattr(row, "route_label", "—") or "—")
        bin_index = getattr(row, "bin_index", None)
        _add("Thùng", str(bin_index) if bin_index is not None else "—")
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


class RecognitionTestDetailDialog(QDialog):
    def __init__(
        self,
        row,
        *,
        on_promote: Callable[[str], None],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Chi tiết lượt kiểm thử")
        self.setMinimumSize(820, 520)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(20)

        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setStyleSheet("background:#000; border-radius:8px;")
        image.setMinimumSize(420, 420)
        path = Path(str(getattr(row, "annotated_image_path", "") or ""))
        pixmap = QPixmap(str(path)) if path.exists() else QPixmap()
        if pixmap.isNull():
            image.setText("(no image)")
        else:
            image.setPixmap(
                pixmap.scaled(
                    420,
                    420,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        outer.addWidget(image, 1)

        info = QVBoxLayout()
        title = QLabel("Recognition QA")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        info.addWidget(title)
        form = QFormLayout()

        def _add(label: str, value: object) -> None:
            left, right = _info_row(label, str(value or "—"))
            right.setWordWrap(True)
            form.addRow(left, right)

        _add("Mẫu", getattr(row, "sample_label", ""))
        _add("Lượt", getattr(row, "trial_number", ""))
        _add("Nhãn thật", getattr(row, "expected_class", ""))
        _add("AI dự đoán", getattr(row, "predicted_class", ""))
        confidence = getattr(row, "confidence", None)
        _add("Confidence", f"{confidence:.3f}" if confidence is not None else "—")
        _add("Kết luận", getattr(row, "verdict", ""))
        _add(
            "Route",
            f"{getattr(row, 'expected_route', '')} → "
            f"{getattr(row, 'predicted_route', '') or '-'}",
        )
        _add("Guard", getattr(row, "guard_reason", ""))
        _add("Loa", getattr(row, "speaker_mode", ""))
        _add("Payload", getattr(row, "uart_payload", ""))
        _add("ACK", getattr(row, "ack_status", ""))
        rtt = getattr(row, "rtt_ms", None)
        _add("RTT", f"{rtt} ms" if rtt is not None else "—")
        _add("Model hash", getattr(row, "model_hash", ""))
        info.addLayout(form)
        info.addStretch()

        actions = QHBoxLayout()
        promote = QPushButton("Đưa vào dữ liệu cải thiện")
        promote.setObjectName("secondary")
        promote.setEnabled(
            int(getattr(row, "detection_count", 0) or 0) == 1
            and not bool(getattr(row, "promoted_path", ""))
        )
        trial_id = str(getattr(row, "id", ""))
        promote.clicked.connect(lambda: (on_promote(trial_id), self.accept()))
        close = QPushButton("Đóng")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        actions.addWidget(promote)
        actions.addStretch()
        actions.addWidget(close)
        info.addLayout(actions)
        outer.addLayout(info, 1)
