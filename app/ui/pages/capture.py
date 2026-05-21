"""Capture tab: low-conf queue review + YOLO format export."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppConfig


class CapturePage(QWidget):
    mode_changed = Signal(str)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(16)

        title = QLabel("Capture & Re-label")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        outer.addWidget(title)

        # mode + counter row
        mode_card = QFrame()
        mode_card.setObjectName("card")
        mode_layout = QHBoxLayout(mode_card)
        mode_layout.setContentsMargins(20, 16, 20, 16)
        mode_layout.setSpacing(20)

        self.rb_off = QRadioButton("Tắt")
        self.rb_manual = QRadioButton("Manual")
        self.rb_auto = QRadioButton("Auto khi conf < threshold")
        self._mode_group = QButtonGroup(self)
        for rb in (self.rb_off, self.rb_manual, self.rb_auto):
            self._mode_group.addButton(rb)
            mode_layout.addWidget(rb)

        if self._cfg.capture.mode == "off":
            self.rb_off.setChecked(True)
        elif self._cfg.capture.mode == "manual":
            self.rb_manual.setChecked(True)
        else:
            self.rb_auto.setChecked(True)

        self.rb_off.toggled.connect(lambda v: v and self.mode_changed.emit("off"))
        self.rb_manual.toggled.connect(lambda v: v and self.mode_changed.emit("manual"))
        self.rb_auto.toggled.connect(lambda v: v and self.mode_changed.emit("auto_low_conf"))

        mode_layout.addStretch()
        self.counter = QLabel("0 ảnh")
        self.counter.setStyleSheet("color: #94A3B8;")
        mode_layout.addWidget(self.counter)

        btn_refresh = QPushButton("↻ Refresh")
        btn_refresh.setObjectName("secondary")
        btn_refresh.clicked.connect(self.reload)
        mode_layout.addWidget(btn_refresh)

        btn_export = QPushButton("⤓ Export YOLO")
        btn_export.setObjectName("primary")
        btn_export.clicked.connect(self._export)
        mode_layout.addWidget(btn_export)

        outer.addWidget(mode_card)

        # grid
        self.grid = QListWidget()
        self.grid.setObjectName("card")
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setIconSize(QSize(160, 120))
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setSpacing(12)
        self.grid.setUniformItemSizes(True)
        outer.addWidget(self.grid, 1)

        self.reload()

    def _queue_dir(self) -> Path:
        return Path(self._cfg.capture.output_dir) / "low_conf_queue"

    def reload(self) -> None:
        self.grid.clear()
        qdir = self._queue_dir()
        if not qdir.exists():
            self.counter.setText("0 ảnh")
            return
        files = sorted(qdir.glob("*.jpg"))
        for f in files:
            meta_file = f.with_suffix(".json")
            label = f.stem[:8]
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    if meta.get("boxes"):
                        b = meta["boxes"][0]
                        label = f"{b.get('cls_name', '?')} {b.get('conf', 0):.2f}"
                except Exception:
                    pass
            pix = QPixmap(str(f)).scaled(
                160, 120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            item = QListWidgetItem(QIcon(pix), label)
            item.setData(Qt.ItemDataRole.UserRole, str(f))
            self.grid.addItem(item)
        self.counter.setText(f"{len(files)} ảnh")

    def _export(self) -> None:
        out = QFileDialog.getExistingDirectory(self, "Export YOLO dataset to…")
        if not out:
            return
        n = export_yolo_dataset(self._queue_dir(), Path(out))
        self.counter.setText(f"Exported {n} ảnh")


def export_yolo_dataset(queue_dir: Path, output_dir: Path) -> int:
    images = output_dir / "images"
    labels = output_dir / "labels"
    images.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)

    classes: dict[int, str] = {}
    n = 0
    if not queue_dir.exists():
        _write_yaml(output_dir, classes)
        return 0
    for jpg in sorted(queue_dir.glob("*.jpg")):
        meta_file = jpg.with_suffix(".json")
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        boxes = meta.get("boxes") or []
        if not boxes:
            continue

        from PIL import Image
        try:
            im = Image.open(jpg)
            w, h = im.size
        except Exception:
            continue

        out_img = images / jpg.name
        out_lbl = labels / (jpg.stem + ".txt")
        if not out_img.exists():
            out_img.write_bytes(jpg.read_bytes())

        lines = []
        for b in boxes:
            cls_id = int(b.get("cls_id", 0))
            cls_name = b.get("cls_name", str(cls_id))
            classes[cls_id] = cls_name
            x1, y1, x2, y2 = b.get("xyxy", [0, 0, 1, 1])
            cx = ((x1 + x2) / 2) / max(w, 1)
            cy = ((y1 + y2) / 2) / max(h, 1)
            bw = (x2 - x1) / max(w, 1)
            bh = (y2 - y1) / max(h, 1)
            lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        out_lbl.write_text("\n".join(lines) + "\n", encoding="utf-8")
        n += 1

    _write_yaml(output_dir, classes)
    return n


def _write_yaml(output_dir: Path, classes: dict[int, str]) -> None:
    if not classes:
        names_block = "names: []"
    else:
        ordered = sorted(classes.items())
        names_block = "names:\n" + "\n".join(f"  {k}: {v}" for k, v in ordered)
    yaml = (
        f"path: {output_dir.as_posix()}\n"
        "train: images\n"
        "val: images\n"
        f"nc: {len(classes)}\n"
        f"{names_block}\n"
    )
    (output_dir / "data.yaml").write_text(yaml, encoding="utf-8")
