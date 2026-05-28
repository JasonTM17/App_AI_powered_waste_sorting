"""Desktop camera annotation dialog for reviewed manual samples."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class AnnotationCanvas(QWidget):
    def __init__(
        self,
        frame_bgr: np.ndarray,
        *,
        initial_bbox: tuple[int, int, int, int] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 420)
        self._frame_size = (0, 0)
        self._pixmap = QPixmap()
        self._bbox = initial_bbox
        self._drag_start: QPoint | None = None
        self._set_frame(frame_bgr)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(800, 500)

    def bbox_xyxy(self) -> tuple[int, int, int, int] | None:
        return self._bbox

    def set_bbox_xyxy(self, bbox: tuple[int, int, int, int] | None) -> None:
        self._bbox = self._clamp_bbox(bbox)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#071120"))
        image_rect = self._image_rect()
        if not self._pixmap.isNull():
            painter.drawPixmap(image_rect, self._pixmap)
        if self._bbox is not None:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor("#34D399"), 3))
            painter.drawRect(self._bbox_to_screen(self._bbox, image_rect))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if not self._image_rect().contains(event.position().toPoint()):
            return
        self._drag_start = event.position().toPoint()
        self._bbox = None
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_start is None:
            return
        self._bbox = self._screen_points_to_bbox(self._drag_start, event.position().toPoint())
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._drag_start is None:
            return
        self._bbox = self._screen_points_to_bbox(self._drag_start, event.position().toPoint())
        self._drag_start = None
        if self._bbox is not None:
            x1, y1, x2, y2 = self._bbox
            if x2 - x1 < 4 or y2 - y1 < 4:
                self._bbox = None
        self.update()

    def _set_frame(self, frame_bgr: np.ndarray) -> None:
        arr = np.asarray(frame_bgr)
        if arr.ndim != 3 or arr.shape[2] < 3:
            raise ValueError("camera frame must be a BGR image")
        rgb = np.ascontiguousarray(arr[:, :, :3][:, :, ::-1])
        height, width = rgb.shape[:2]
        self._frame_size = (width, height)
        qimage = QImage(rgb.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()
        self._pixmap = QPixmap.fromImage(qimage)
        self._bbox = self._clamp_bbox(self._bbox)

    def _image_rect(self) -> QRect:
        width, height = self._frame_size
        if width <= 0 or height <= 0:
            return QRect()
        scale = min(self.width() / width, self.height() / height)
        draw_width = max(1, int(width * scale))
        draw_height = max(1, int(height * scale))
        return QRect(
            (self.width() - draw_width) // 2,
            (self.height() - draw_height) // 2,
            draw_width,
            draw_height,
        )

    def _screen_points_to_bbox(self, first: QPoint, second: QPoint) -> tuple[int, int, int, int] | None:
        image_rect = self._image_rect()
        a = self._screen_to_image(first, image_rect)
        b = self._screen_to_image(second, image_rect)
        if a is None or b is None:
            return None
        x1, x2 = sorted((a[0], b[0]))
        y1, y2 = sorted((a[1], b[1]))
        return self._clamp_bbox((x1, y1, x2, y2))

    def _screen_to_image(self, point: QPoint, image_rect: QRect) -> tuple[int, int] | None:
        if image_rect.width() <= 0 or image_rect.height() <= 0:
            return None
        clamped_x = max(image_rect.left(), min(image_rect.right(), point.x()))
        clamped_y = max(image_rect.top(), min(image_rect.bottom(), point.y()))
        width, height = self._frame_size
        x = int((clamped_x - image_rect.left()) * width / image_rect.width())
        y = int((clamped_y - image_rect.top()) * height / image_rect.height())
        return x, y

    def _bbox_to_screen(self, bbox: tuple[int, int, int, int], image_rect: QRect) -> QRect:
        width, height = self._frame_size
        x1, y1, x2, y2 = bbox
        sx1 = image_rect.left() + int(x1 * image_rect.width() / max(width, 1))
        sy1 = image_rect.top() + int(y1 * image_rect.height() / max(height, 1))
        sx2 = image_rect.left() + int(x2 * image_rect.width() / max(width, 1))
        sy2 = image_rect.top() + int(y2 * image_rect.height() / max(height, 1))
        return QRect(sx1, sy1, max(1, sx2 - sx1), max(1, sy2 - sy1))

    def _clamp_bbox(self, bbox: tuple[int, int, int, int] | None) -> tuple[int, int, int, int] | None:
        if bbox is None:
            return None
        width, height = self._frame_size
        x1, y1, x2, y2 = (int(value) for value in bbox)
        left = max(0, min(width, min(x1, x2)))
        top = max(0, min(height, min(y1, y2)))
        right = max(0, min(width, max(x1, x2)))
        bottom = max(0, min(height, max(y1, y2)))
        if right <= left or bottom <= top:
            return None
        return left, top, right, bottom


class CameraAnnotationDialog(QDialog):
    def __init__(
        self,
        frame_bgr: np.ndarray,
        *,
        class_name: str,
        initial_bbox: tuple[int, int, int, int] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Chụp & gắn nhãn")
        self._approve_now = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        title = QLabel(f"Nhãn: {class_name}")
        title.setObjectName("h2")
        layout.addWidget(title)
        hint = QLabel("Kéo trên ảnh để vẽ lại bbox nếu gợi ý chưa đúng.")
        hint.setObjectName("muted")
        layout.addWidget(hint)
        self.canvas = AnnotationCanvas(frame_bgr, initial_bbox=initial_bbox)
        layout.addWidget(self.canvas, 1)
        actions = QHBoxLayout()
        actions.addStretch()
        pending = QPushButton("Lưu cần duyệt")
        pending.setObjectName("secondary")
        pending.clicked.connect(self._accept_pending)
        approved = QPushButton("Lưu đã duyệt")
        approved.setObjectName("primary")
        approved.clicked.connect(self._accept_approved)
        cancel = QPushButton("Hủy")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        actions.addWidget(pending)
        actions.addWidget(approved)
        actions.addWidget(cancel)
        layout.addLayout(actions)

    def bbox_xyxy(self) -> tuple[int, int, int, int] | None:
        return self.canvas.bbox_xyxy()

    def approve_now(self) -> bool:
        return self._approve_now

    def _accept_approved(self) -> None:
        self._approve_now = True
        self.accept()

    def _accept_pending(self) -> None:
        self._approve_now = False
        self.accept()


__all__ = ["AnnotationCanvas", "CameraAnnotationDialog"]
