"""Capture tab: low-conf queue review + YOLO format export."""

from __future__ import annotations

import json
import shutil
import uuid
from collections import Counter
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppConfig
from app.core.dataset_catalog import DatasetCatalog
from app.core.waste_categories import DEFAULT_CLASS_ORDER, default_class_id_for_name
from app.utils.dataset_import import import_yolo_dataset_to_queue, label_map_for_preset
from app.utils.paths import dataset_db_path, resource_path

DISPLAY_LIMIT = 200
TRUSTED_SOURCES = {"auto_low_conf", "manual_import", "manual_camera_capture", "roboflow"}
REVIEW_REQUIRED_SOURCES = {"auto_low_conf", "manual_camera_capture"}


class CapturePage(QWidget):
    mode_changed = Signal(str)
    open_web_requested = Signal()
    capture_camera_sample_requested = Signal(str)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self._catalog_path = dataset_db_path()
        self._sync_thread: CatalogSyncThread | None = None
        self._queue_files_cache: tuple[Path, int, list[Path]] | None = None
        self._queue_count_cache: tuple[Path, int, int] | None = None
        self._catalog_summary_cache: tuple[int, dict] | None = None
        self._label_cache: dict[str, tuple[int, str]] = {}
        self._icon_cache: dict[str, tuple[int, QIcon]] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(16)

        title = QLabel("Data & Gán nhãn")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        outer.addWidget(title)

        # mode + action rows
        mode_card = QFrame()
        mode_card.setObjectName("card")
        mode_layout = QVBoxLayout(mode_card)
        mode_layout.setContentsMargins(20, 16, 20, 16)
        mode_layout.setSpacing(12)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(20)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        catalog_row = QHBoxLayout()
        catalog_row.setSpacing(10)
        mode_layout.addLayout(mode_row)
        mode_layout.addLayout(action_row)
        mode_layout.addLayout(catalog_row)

        self.rb_off = QRadioButton("Tắt")
        self.rb_manual = QRadioButton("Manual")
        self.rb_auto = QRadioButton("Auto khi conf < threshold")
        self._mode_group = QButtonGroup(self)
        for rb in (self.rb_off, self.rb_manual, self.rb_auto):
            self._mode_group.addButton(rb)
            mode_row.addWidget(rb)

        if self._cfg.capture.mode == "off":
            self.rb_off.setChecked(True)
        elif self._cfg.capture.mode == "manual":
            self.rb_manual.setChecked(True)
        else:
            self.rb_auto.setChecked(True)

        self.rb_off.toggled.connect(lambda v: v and self.mode_changed.emit("off"))
        self.rb_manual.toggled.connect(lambda v: v and self.mode_changed.emit("manual"))
        self.rb_auto.toggled.connect(lambda v: v and self.mode_changed.emit("auto_low_conf"))

        mode_row.addStretch()

        self.class_select = QComboBox()
        self.class_select.setMinimumWidth(220)
        for _cls_id, name in self._class_options():
            self.class_select.addItem(name)
        pen_idx = self.class_select.findText("Pen")
        if pen_idx >= 0:
            self.class_select.setCurrentIndex(pen_idx)
        action_row.addWidget(self.class_select)

        btn_add_manual = QPushButton("Thêm ảnh thủ công")
        btn_add_manual.setObjectName("secondary")
        _fit_button_to_text(btn_add_manual, 150)
        btn_add_manual.clicked.connect(self._add_manual_images)
        action_row.addWidget(btn_add_manual)

        btn_capture_camera = QPushButton("Ghi frame camera")
        btn_capture_camera.setObjectName("secondary")
        btn_capture_camera.setToolTip(
            "Luu frame hien tai vao queue; can chinh box bang Web annotate truoc khi train."
        )
        _fit_button_to_text(btn_capture_camera, 145)
        btn_capture_camera.clicked.connect(self._capture_camera_sample)
        action_row.addWidget(btn_capture_camera)

        btn_import_yolo = QPushButton("Nhập YOLO/Roboflow ZIP")
        btn_import_yolo.setObjectName("secondary")
        _fit_button_to_text(btn_import_yolo, 170)
        btn_import_yolo.clicked.connect(self._import_yolo_zip)
        action_row.addWidget(btn_import_yolo)

        btn_relabel = QPushButton("Đổi nhãn ảnh chọn")
        btn_relabel.setObjectName("secondary")
        _fit_button_to_text(btn_relabel, 160)
        btn_relabel.clicked.connect(self._relabel_selected)
        action_row.addWidget(btn_relabel)

        btn_delete = QPushButton("Xóa ảnh chọn")
        btn_delete.setObjectName("secondary")
        _fit_button_to_text(btn_delete, 130)
        btn_delete.clicked.connect(self._delete_selected)
        action_row.addWidget(btn_delete)

        btn_quarantine = QPushButton("Cách ly data lạ")
        btn_quarantine.setObjectName("secondary")
        _fit_button_to_text(btn_quarantine, 130)
        btn_quarantine.clicked.connect(self._quarantine_untrusted)
        action_row.addWidget(btn_quarantine)
        action_row.addStretch()

        self.counter = QLabel("0 ảnh")
        self.counter.setStyleSheet("color: #94A3B8;")
        mode_row.addWidget(self.counter)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setObjectName("secondary")
        _fit_button_to_text(btn_refresh, 90)
        btn_refresh.clicked.connect(self.reload)
        catalog_row.addWidget(btn_refresh)

        self.btn_sync_db = QPushButton("Đồng bộ CSDL")
        self.btn_sync_db.setObjectName("secondary")
        _fit_button_to_text(self.btn_sync_db, 130)
        self.btn_sync_db.clicked.connect(self._sync_catalog)
        catalog_row.addWidget(self.btn_sync_db)

        btn_open_web = QPushButton("Mở Web annotate")
        btn_open_web.setObjectName("secondary")
        _fit_button_to_text(btn_open_web, 140)
        btn_open_web.clicked.connect(self._open_web_annotate)
        catalog_row.addWidget(btn_open_web)

        btn_export = QPushButton("Export YOLO")
        btn_export.setObjectName("primary")
        _fit_button_to_text(btn_export, 110)
        btn_export.clicked.connect(self._export)
        catalog_row.addWidget(btn_export)
        catalog_row.addStretch()

        outer.addWidget(mode_card)

        self.stats = QLabel("")
        self.stats.setObjectName("muted")
        self.stats.setWordWrap(True)
        outer.addWidget(self.stats)

        # grid
        self.grid = QListWidget()
        self.grid.setObjectName("card")
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setIconSize(QSize(160, 120))
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.grid.setSpacing(12)
        self.grid.setUniformItemSizes(True)
        outer.addWidget(self.grid, 1)

        self.reload()

    def _queue_dir(self) -> Path:
        return _resolve_queue_dir(self._cfg.capture.output_dir, self._catalog_path)

    def _class_options(self) -> list[tuple[int, str]]:
        by_name = _model_class_ids(self._cfg.model.path)
        merged = dict(by_name)
        next_id = max(merged.values(), default=-1) + 1
        for name in [*DEFAULT_CLASS_ORDER, *(m.class_name for m in self._cfg.mappings)]:
            if name in merged:
                continue
            cls_id = default_class_id_for_name(name)
            if cls_id is None or cls_id in merged.values():
                cls_id = next_id
                next_id += 1
            merged[name] = cls_id
        return sorted((cls_id, name) for name, cls_id in merged.items())

    def _class_ids(self) -> dict[str, int]:
        return {name: cls_id for cls_id, name in self._class_options()}

    def reload(self) -> None:
        self.grid.clear()
        qdir = self._queue_dir()
        if not qdir.exists():
            self._update_stats()
            return
        files = self._queue_files(qdir)
        visible_files = files[:DISPLAY_LIMIT]
        for f in visible_files:
            item = QListWidgetItem(self._icon_for_image(f), self._label_for_image(f))
            item.setData(Qt.ItemDataRole.UserRole, str(f))
            self.grid.addItem(item)
        self._prune_image_caches(visible_files)
        self._update_stats(displayed=min(len(files), DISPLAY_LIMIT))

    def _update_stats(self, displayed: int | None = None) -> None:
        summary, catalog_total = self._summary_for_stats()
        catalog_text = f"CSDL: {catalog_total} bản ghi"
        if catalog_total != summary["images"]:
            catalog_text += " (lệch, bấm Đồng bộ CSDL)"
        self.counter.setText(f"{summary['images']} ảnh")
        classes = summary["classes"]
        class_text = ", ".join(f"{name}: {count}" for name, count in classes.most_common(5))
        if not class_text:
            class_text = "chưa có nhãn"
        self.stats.setText(
            f"Data hiện có: {summary['images']} ảnh, {summary['boxes']} box, "
            f"{len(classes)} nhãn. Auto: {summary['auto']}, thủ công: {summary['manual']}, "
            f"Roboflow: {summary['roboflow']}, data lạ: {summary['untrusted']}. "
            f"{catalog_text}. "
            f"Phân bố: {class_text}"
            + (
                f". Đang hiển thị {displayed} ảnh đầu tiên để app chạy mượt."
                if displayed is not None and summary["images"] > displayed
                else ""
            )
        )

    def _export(self) -> None:
        out = QFileDialog.getExistingDirectory(self, "Export YOLO dataset to...")
        if not out:
            return
        n = export_yolo_dataset(self._queue_dir(), Path(out))
        self.counter.setText(f"Exported {n} ảnh")

    def _open_web_annotate(self) -> None:
        self.open_web_requested.emit()

    def _add_manual_images(self) -> None:
        cls_name = self.class_select.currentText().strip()
        if not cls_name:
            QMessageBox.warning(self, "Thiếu nhãn", "Vui lòng chọn nhãn trước khi thêm ảnh.")
            return
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn ảnh data",
            "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp)",
        )
        if not files:
            return
        class_ids = self._class_ids()
        cls_id = class_ids.get(cls_name, self.class_select.currentIndex())
        added = import_manual_images(
            files,
            self._queue_dir(),
            cls_name,
            cls_id,
            catalog_path=self._catalog_path,
        )
        self._invalidate_queue_cache()
        self.reload()
        self.counter.setText(f"Đã thêm {added} ảnh")

    def _capture_camera_sample(self) -> None:
        cls_name = self.class_select.currentText().strip()
        if not cls_name:
            QMessageBox.warning(self, "Thieu nhan", "Chon nhan truoc khi ghi frame camera.")
            return
        self.capture_camera_sample_requested.emit(cls_name)

    def _import_yolo_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn Roboflow/YOLO ZIP",
            "",
            "YOLO dataset (*.zip)",
        )
        if not path:
            return
        imported = import_yolo_dataset_to_queue(
            Path(path),
            self._queue_dir(),
            source_name="roboflow",
            catalog_path=self._catalog_path,
            class_name_to_id=self._class_ids(),
            label_map=label_map_for_preset("pen_hardware_downloads"),
        )
        self._invalidate_queue_cache()
        self.reload()
        QMessageBox.information(self, "Nhập data xong", f"Đã nhập {imported} ảnh từ YOLO ZIP.")

    def _selected_paths(self) -> list[Path]:
        paths: list[Path] = []
        for item in self.grid.selectedItems():
            raw = item.data(Qt.ItemDataRole.UserRole)
            if raw:
                paths.append(Path(str(raw)))
        return paths

    def _relabel_selected(self) -> None:
        paths = self._selected_paths()
        if not paths:
            QMessageBox.information(self, "Chưa chọn ảnh", "Vui lòng chọn một hoặc nhiều ảnh trong lưới.")
            return
        cls_name = self.class_select.currentText().strip()
        class_ids = self._class_ids()
        cls_id = class_ids.get(cls_name, self.class_select.currentIndex())
        changed = relabel_images(paths, cls_name, cls_id, catalog_path=self._catalog_path)
        self._invalidate_queue_cache()
        self.reload()
        self.counter.setText(f"Đã đổi nhãn {changed} ảnh")

    def _delete_selected(self) -> None:
        paths = self._selected_paths()
        if not paths:
            QMessageBox.information(self, "Chưa chọn ảnh", "Vui lòng chọn ảnh cần xóa.")
            return
        ok = QMessageBox.question(
            self,
            "Xóa data",
            f"Xóa {len(paths)} ảnh đã chọn khỏi queue?",
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        removed = delete_queue_items(paths, catalog_path=self._catalog_path)
        self._invalidate_queue_cache()
        self.reload()
        self.counter.setText(f"Đã xóa {removed} ảnh")

    def _quarantine_untrusted(self) -> None:
        count = summarize_queue(self._queue_dir())["untrusted"]
        if not count:
            QMessageBox.information(self, "Data sạch", "Không có data lạ cần cách ly.")
            return
        ok = QMessageBox.question(
            self,
            "Cách ly data lạ",
            f"Chuyển {count} ảnh không rõ nguồn ra thư mục quarantine?",
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        moved = quarantine_untrusted_items(self._queue_dir(), catalog_path=self._catalog_path)
        self._invalidate_queue_cache()
        self.reload()
        self.counter.setText(f"Đã cách ly {moved} ảnh")

    def _sync_catalog(self) -> None:
        if self._sync_thread is not None and self._sync_thread.isRunning():
            return
        qdir = self._queue_dir()
        self.btn_sync_db.setEnabled(False)
        self.btn_sync_db.setText("Đang đồng bộ...")
        self.counter.setText("Đang đồng bộ CSDL...")
        self.stats.setText(f"Đang đọc queue và cập nhật CSDL từ: {qdir}")
        worker = CatalogSyncThread(self._catalog_path, qdir)
        worker.done.connect(self._on_sync_catalog_done)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(self._on_sync_catalog_finished)
        self._sync_thread = worker
        worker.start()

    def _on_sync_catalog_done(self, ok: bool, indexed: int, message: str) -> None:
        self.btn_sync_db.setEnabled(True)
        self.btn_sync_db.setText("Đồng bộ CSDL")
        if ok:
            self._catalog_summary_cache = None
        self._update_stats(displayed=self.grid.count() or None)
        if ok:
            self.counter.setText(f"Đã đồng bộ {indexed} bản ghi")
            return
        self.counter.setText("Đồng bộ CSDL lỗi")
        QMessageBox.warning(self, "Đồng bộ CSDL lỗi", message)

    def _on_sync_catalog_finished(self) -> None:
        self._sync_thread = None

    def _summary_for_stats(self) -> tuple[dict, int]:
        qdir = self._queue_dir()
        catalog_summary = self._catalog_summary()
        catalog_total = int(catalog_summary["images"]) if catalog_summary is not None else 0
        queue_images = self._queue_image_count(qdir)
        if catalog_summary is not None and catalog_total > 0 and catalog_total == queue_images:
            return catalog_summary, catalog_total
        return summarize_queue(qdir), catalog_total

    def _catalog_summary(self) -> dict | None:
        mtime_ns = _safe_mtime_ns(self._catalog_path)
        if self._catalog_summary_cache is not None and self._catalog_summary_cache[0] == mtime_ns:
            return self._catalog_summary_cache[1]
        try:
            catalog = DatasetCatalog(self._catalog_path)
            try:
                sources = catalog.count_by_source()
                classes = Counter(catalog.count_box_classes())
                summary = {
                    "images": catalog.count_total(),
                    "boxes": catalog.count_boxes_total(),
                    "classes": classes,
                    "auto": sources.get("auto_low_conf", 0),
                    "manual": sources.get("manual_import", 0)
                    + sources.get("manual_camera_capture", 0),
                    "roboflow": sum(
                        count
                        for source, count in sources.items()
                        if source == "roboflow" or source.startswith("roboflow_")
                    ),
                    "untrusted": sum(
                        count
                        for source, count in sources.items()
                        if not _trusted_source_name(source)
                    ),
                }
                self._catalog_summary_cache = (_safe_mtime_ns(self._catalog_path), summary)
                return summary
            finally:
                catalog.close()
        except Exception:
            return None

    def _queue_files(self, qdir: Path) -> list[Path]:
        key_path = qdir.resolve()
        mtime_ns = _safe_mtime_ns(qdir)
        if (
            self._queue_files_cache is not None
            and self._queue_files_cache[0] == key_path
            and self._queue_files_cache[1] == mtime_ns
        ):
            return self._queue_files_cache[2]
        files = sorted(qdir.glob("*.jpg"))
        self._queue_files_cache = (key_path, mtime_ns, files)
        self._queue_count_cache = (key_path, mtime_ns, len(files))
        return files

    def _queue_image_count(self, qdir: Path) -> int:
        key_path = qdir.resolve()
        mtime_ns = _safe_mtime_ns(qdir)
        if (
            self._queue_count_cache is not None
            and self._queue_count_cache[0] == key_path
            and self._queue_count_cache[1] == mtime_ns
        ):
            return self._queue_count_cache[2]
        count = _count_queue_images(qdir)
        self._queue_count_cache = (key_path, mtime_ns, count)
        return count

    def _label_for_image(self, image_path: Path) -> str:
        meta_file = image_path.with_suffix(".json")
        key = str(meta_file)
        mtime_ns = _safe_mtime_ns(meta_file)
        cached = self._label_cache.get(key)
        if cached is not None and cached[0] == mtime_ns:
            return cached[1]
        label = image_path.stem[:8]
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if meta.get("boxes"):
                    box = meta["boxes"][0]
                    label = f"{box.get('cls_name', '?')} {box.get('conf', 0):.2f}"
            except Exception:
                pass
        self._label_cache[key] = (mtime_ns, label)
        return label

    def _icon_for_image(self, image_path: Path) -> QIcon:
        key = str(image_path)
        mtime_ns = _safe_mtime_ns(image_path)
        cached = self._icon_cache.get(key)
        if cached is not None and cached[0] == mtime_ns:
            return cached[1]
        pix = QPixmap(str(image_path)).scaled(
            160,
            120,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        icon = QIcon(pix)
        self._icon_cache[key] = (mtime_ns, icon)
        return icon

    def _prune_image_caches(self, visible_files: list[Path]) -> None:
        if len(self._icon_cache) <= DISPLAY_LIMIT * 2 and len(self._label_cache) <= DISPLAY_LIMIT * 2:
            return
        visible_images = {str(path) for path in visible_files}
        visible_meta = {str(path.with_suffix(".json")) for path in visible_files}
        self._icon_cache = {
            key: value for key, value in self._icon_cache.items() if key in visible_images
        }
        self._label_cache = {
            key: value for key, value in self._label_cache.items() if key in visible_meta
        }

    def _invalidate_queue_cache(self) -> None:
        self._queue_files_cache = None
        self._queue_count_cache = None
        self._catalog_summary_cache = None
        self._label_cache.clear()
        self._icon_cache.clear()

    def _dataset_catalog_total(self) -> int:
        try:
            catalog = DatasetCatalog(self._catalog_path)
            try:
                return catalog.count_total()
            finally:
                catalog.close()
        except Exception:
            return 0


def _fit_button_to_text(button: QPushButton, minimum: int) -> None:
    button.setMinimumWidth(max(minimum, button.sizeHint().width() + 12))


class CatalogSyncThread(QThread):
    done = Signal(bool, int, str)

    def __init__(self, catalog_path: Path, queue_dir: Path):
        super().__init__()
        self._catalog_path = catalog_path
        self._queue_dir = queue_dir

    def run(self) -> None:
        try:
            catalog = DatasetCatalog(self._catalog_path)
            try:
                indexed = catalog.index_queue(self._queue_dir)
            finally:
                catalog.close()
        except Exception as exc:
            self.done.emit(False, 0, str(exc))
        else:
            self.done.emit(True, indexed, "")


def _resolve_queue_dir(output_dir: str, catalog_path: Path) -> Path:
    output_path = Path(output_dir).expanduser()
    candidates: list[Path] = []

    def add_candidate(path: Path) -> None:
        resolved = path.resolve() if path.exists() else path
        if resolved not in candidates:
            candidates.append(resolved)

    if output_path.is_absolute():
        add_candidate(output_path / "low_conf_queue")
    else:
        for base in (Path.cwd(), resource_path("."), Path(__file__).resolve().parent):
            base_dir = base if base.is_dir() else base.parent
            for parent in (base_dir, *base_dir.parents):
                add_candidate(parent / output_path / "low_conf_queue")
                add_candidate(parent / "trash-sorter-v2" / output_path / "low_conf_queue")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    inferred = _queue_dir_from_catalog(catalog_path)
    if inferred is not None:
        return inferred

    return candidates[0] if candidates else output_path / "low_conf_queue"


def _queue_dir_from_catalog(catalog_path: Path) -> Path | None:
    try:
        catalog = DatasetCatalog(catalog_path)
        try:
            rows, _total = catalog.list_items(limit=1)
        finally:
            catalog.close()
    except Exception:
        return None
    if not rows:
        return None
    image_path = Path(str(rows[0].get("image_path") or ""))
    queue_dir = image_path.parent
    return queue_dir if queue_dir.exists() else None


def _count_queue_images(queue_dir: Path) -> int:
    if not queue_dir.exists():
        return 0
    return sum(1 for _ in queue_dir.glob("*.jpg"))


def _safe_mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return -1


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
        if not _is_trainable_meta(meta):
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


def import_manual_images(
    image_paths: list[str] | tuple[str, ...],
    queue_dir: Path,
    cls_name: str,
    cls_id: int,
    *,
    catalog_path: Path | None = None,
) -> int:
    """Import user-selected images as labeled queue items."""
    from PIL import Image

    queue_dir.mkdir(parents=True, exist_ok=True)
    catalog = DatasetCatalog(catalog_path) if catalog_path is not None else None
    added = 0
    try:
        for raw in image_paths:
            src = Path(raw)
            if not src.exists():
                continue
            try:
                with Image.open(src) as im:
                    rgb = im.convert("RGB")
                    w, h = rgb.size
                    uid = uuid.uuid4().hex[:12]
                    img_path = queue_dir / f"manual_{uid}.jpg"
                    rgb.save(img_path, format="JPEG", quality=92)
            except Exception:
                continue

            meta = {
                "ts": datetime.now().isoformat(),
                "source": "manual_import",
                "original_file": str(src),
                "boxes": [
                    {
                        "cls_id": int(cls_id),
                        "cls_name": cls_name,
                        "conf": 1.0,
                        "xyxy": [0, 0, w, h],
                    }
                ],
            }
            img_path.with_suffix(".json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            if catalog is not None:
                catalog.upsert_item(img_path, meta)
            added += 1
        return added
    finally:
        if catalog is not None:
            catalog.close()


def summarize_queue(queue_dir: Path) -> dict:
    images = sorted(queue_dir.glob("*.jpg")) if queue_dir.exists() else []
    classes: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    boxes = 0
    missing_meta = 0
    untrusted = 0
    for img in images:
        meta_file = img.with_suffix(".json")
        if not meta_file.exists():
            missing_meta += 1
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            missing_meta += 1
            continue
        source = meta.get("source") or "unknown"
        sources[source] += 1
        if not _is_trusted_meta(meta):
            untrusted += 1
        for box in meta.get("boxes") or []:
            boxes += 1
            classes[box.get("cls_name") or "?"] += 1
    return {
        "images": len(images),
        "boxes": boxes,
        "classes": classes,
        "auto": sources.get("auto_low_conf", 0),
        "manual": sources.get("manual_import", 0) + sources.get("manual_camera_capture", 0),
        "roboflow": sum(
            count
            for source, count in sources.items()
            if source == "roboflow" or source.startswith("roboflow_")
        ),
        "unknown": sources.get("unknown", 0),
        "untrusted": untrusted,
        "missing_meta": missing_meta,
    }


def relabel_images(
    image_paths: list[Path],
    cls_name: str,
    cls_id: int,
    *,
    catalog_path: Path | None = None,
) -> int:
    catalog = DatasetCatalog(catalog_path) if catalog_path is not None else None
    changed = 0
    try:
        for img in image_paths:
            meta_file = img.with_suffix(".json")
            if not img.exists() or not meta_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            boxes = meta.get("boxes") or []
            if not boxes:
                continue
            for box in boxes:
                box["cls_id"] = int(cls_id)
                box["cls_name"] = cls_name
                box["conf"] = 1.0
            meta["reviewed"] = True
            meta["reviewed_at"] = datetime.now().isoformat()
            meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            if catalog is not None:
                catalog.upsert_item(img, meta)
            changed += 1
        return changed
    finally:
        if catalog is not None:
            catalog.close()


def delete_queue_items(image_paths: list[Path], *, catalog_path: Path | None = None) -> int:
    removed = 0
    removed_paths: list[Path] = []
    for img in image_paths:
        existed = img.exists()
        try:
            img.unlink(missing_ok=True)
            img.with_suffix(".json").unlink(missing_ok=True)
        except OSError:
            continue
        if existed:
            removed += 1
            removed_paths.append(img)
    if catalog_path is not None and removed_paths:
        catalog = DatasetCatalog(catalog_path)
        try:
            catalog.delete_by_image_paths(removed_paths)
        finally:
            catalog.close()
    return removed


def quarantine_untrusted_items(queue_dir: Path, *, catalog_path: Path | None = None) -> int:
    if not queue_dir.exists():
        return 0
    target = queue_dir.parent / "quarantine" / datetime.now().strftime("%Y%m%d_%H%M%S")
    moved = 0
    moved_paths: list[Path] = []
    for img in sorted(queue_dir.glob("*.jpg")):
        meta_file = img.with_suffix(".json")
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        if _is_trusted_meta(meta):
            continue
        target.mkdir(parents=True, exist_ok=True)
        shutil.move(str(img), str(target / img.name))
        shutil.move(str(meta_file), str(target / meta_file.name))
        moved += 1
        moved_paths.append(img)
    if catalog_path is not None and moved_paths:
        catalog = DatasetCatalog(catalog_path)
        try:
            catalog.delete_by_image_paths(moved_paths)
        finally:
            catalog.close()
    return moved


def _is_trusted_meta(meta: dict) -> bool:
    source = str(meta.get("source") or "unknown")
    if not _trusted_source_name(source):
        return False
    return not meta.get("unknown_labels")


def _is_trainable_meta(meta: dict) -> bool:
    if not _is_trusted_meta(meta):
        return False
    source = str(meta.get("source") or "unknown")
    return not (source in REVIEW_REQUIRED_SOURCES and not meta.get("reviewed"))


def _trusted_source_name(source: str) -> bool:
    source = str(source or "unknown")
    return source not in {"unknown", "untrusted"}


def _model_class_ids(model_path: str) -> dict[str, int]:
    resolved = resource_path(model_path)
    return dict(_cached_model_class_ids(str(resolved), _safe_mtime_ns(resolved)))


@lru_cache(maxsize=4)
def _cached_model_class_ids(resolved_model_path: str, mtime_ns: int) -> tuple[tuple[str, int], ...]:
    _ = mtime_ns
    try:
        from ultralytics import YOLO

        model = YOLO(resolved_model_path)
        return tuple((name, int(cls_id)) for cls_id, name in dict(model.names).items())
    except Exception:
        return ()
