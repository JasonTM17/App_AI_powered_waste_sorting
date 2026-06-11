"""Capture tab: low-conf queue review + YOLO format export."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
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
from app.core.dataset_review import (
    DatasetReviewError,
    DatasetReviewRequest,
    apply_dataset_review_action,
)
from app.core.dataset_trust import (
    DatasetTrustState,
    classify_dataset_item,
    is_trusted_source_name,
)
from app.core.hard_negative_dataset import HARD_NEGATIVE_REASON_LABELS, HARD_NEGATIVE_REASONS
from app.core.waste_categories import (
    DEFAULT_CLASS_ORDER,
    canonical_class_name,
    default_class_id_for_name,
)
from app.utils.dataset_import import import_yolo_dataset_to_queue, label_map_for_preset
from app.utils.paths import dataset_db_path, resource_path

DISPLAY_LIMIT = 200

class CapturePage(QWidget):
    mode_changed = Signal(str)
    open_web_requested = Signal()
    capture_camera_sample_requested = Signal(str)
    camera_annotation_requested = Signal(str, int)
    capture_reviewed_camera_sample_requested = Signal(str, int, object, bool)
    capture_hard_negative_requested = Signal(str)
    learn_now_status_requested = Signal(str)
    learn_now_refresh_requested = Signal(str)
    learn_now_train_requested = Signal(str, str)
    training_stop_requested = Signal()
    training_status_requested = Signal()
    candidate_model_test_requested = Signal(str)

    def __init__(
        self,
        cfg: AppConfig,
        parent=None,
        title_text: str = "Data & Gán nhãn",
        *,
        show_training_panel: bool = False,
    ):
        super().__init__(parent)
        self._cfg = cfg
        self._show_training_panel = show_training_panel
        self._catalog_path = dataset_db_path()
        self._sync_thread: CatalogSyncThread | None = None
        self._queue_files_cache: tuple[Path, int, list[Path]] | None = None
        self._display_files_cache: tuple[Path, int, int, list[Path]] | None = None
        self._queue_count_cache: tuple[Path, int, int] | None = None
        self._catalog_summary_cache: tuple[int, dict] | None = None
        self._label_cache: dict[str, tuple[int, str]] = {}
        self._icon_cache: dict[str, tuple[int, QIcon]] = {}
        self._loaded = False
        self._learn_now_status: dict[str, object] = {}
        self._training_status: dict[str, object] = {}
        self._training_timer = QTimer(self)
        self._training_timer.setInterval(2500)
        self._training_timer.timeout.connect(self.training_status_requested.emit)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(16)

        title = QLabel(title_text)
        title.setObjectName("h1")
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
        manage_row = QHBoxLayout()
        manage_row.setSpacing(10)
        catalog_row = QHBoxLayout()
        catalog_row.setSpacing(10)
        mode_layout.addLayout(mode_row)
        mode_layout.addLayout(action_row)
        mode_layout.addLayout(manage_row)
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
        if self._show_training_panel:
            self.class_select.currentTextChanged.connect(lambda _value: self._request_learn_status())
        action_row.addWidget(self.class_select)

        btn_add_manual = QPushButton("Thêm ảnh thủ công")
        btn_add_manual.setObjectName("secondary")
        _fit_button_to_text(btn_add_manual, 150)
        btn_add_manual.clicked.connect(self._add_manual_images)
        btn_add_manual.setVisible(self._show_training_panel)
        manage_row.addWidget(btn_add_manual)

        btn_capture_camera = QPushButton("Ghi frame camera")
        btn_capture_camera.setObjectName("secondary")
        btn_capture_camera.setToolTip(
            "Lưu frame hiện tại vào queue; cần chỉnh box bằng Web annotate trước khi train."
        )
        _fit_button_to_text(btn_capture_camera, 145)
        btn_capture_camera.clicked.connect(self._capture_camera_sample)
        action_row.addWidget(btn_capture_camera)

        btn_annotate_camera = QPushButton("Chụp & gắn nhãn")
        btn_annotate_camera.setObjectName("secondary")
        btn_annotate_camera.setToolTip(
            "Chụp frame hiện tại, vẽ bbox ngay trong app và lưu mẫu đã duyệt để train."
        )
        _fit_button_to_text(btn_annotate_camera, 145)
        btn_annotate_camera.clicked.connect(self._request_camera_annotation)
        btn_annotate_camera.setVisible(self._show_training_panel)
        action_row.addWidget(btn_annotate_camera)

        self.hard_negative_reason_select = QComboBox()
        self.hard_negative_reason_select.setMinimumWidth(170)
        for reason in HARD_NEGATIVE_REASONS:
            self.hard_negative_reason_select.addItem(HARD_NEGATIVE_REASON_LABELS[reason], reason)
        action_row.addWidget(self.hard_negative_reason_select)

        btn_capture_negative = QPushButton("Ghi negative")
        btn_capture_negative.setObjectName("secondary")
        btn_capture_negative.setToolTip(
            "Lưu frame tay/vải/nền/2 vật làm safety eval. Mẫu này không được đưa vào train YOLO."
        )
        _fit_button_to_text(btn_capture_negative, 125)
        btn_capture_negative.clicked.connect(self._capture_hard_negative)
        action_row.addWidget(btn_capture_negative)

        btn_import_yolo = QPushButton("Nhập YOLO/Roboflow ZIP")
        btn_import_yolo.setObjectName("secondary")
        _fit_button_to_text(btn_import_yolo, 170)
        btn_import_yolo.clicked.connect(self._import_yolo_zip)
        manage_row.addWidget(btn_import_yolo)

        btn_relabel = QPushButton("Đổi nhãn ảnh chọn")
        btn_relabel.setObjectName("secondary")
        _fit_button_to_text(btn_relabel, 160)
        btn_relabel.clicked.connect(self._relabel_selected)
        manage_row.addWidget(btn_relabel)

        btn_delete = QPushButton("Xóa ảnh chọn")
        btn_delete.setObjectName("secondary")
        _fit_button_to_text(btn_delete, 130)
        btn_delete.clicked.connect(self._delete_selected)
        manage_row.addWidget(btn_delete)

        btn_quarantine = QPushButton("Cách ly data lạ")
        btn_quarantine.setObjectName("secondary")
        _fit_button_to_text(btn_quarantine, 130)
        btn_quarantine.clicked.connect(self._quarantine_untrusted)
        manage_row.addWidget(btn_quarantine)
        manage_row.addStretch()
        action_row.addStretch()

        self.counter = QLabel("0 ảnh")
        self.counter.setObjectName("mono")
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

        train_card = QFrame()
        train_card.setObjectName("card")
        train_layout = QVBoxLayout(train_card)
        train_layout.setContentsMargins(20, 16, 20, 16)
        train_layout.setSpacing(10)
        train_header = QHBoxLayout()
        train_header.setSpacing(10)
        train_title = QLabel("Huấn luyện thủ công")
        train_title.setObjectName("sectionTitle")
        train_header.addWidget(train_title)
        train_header.addStretch()
        self.learn_route = QLabel("Route: -")
        self.learn_route.setObjectName("mono")
        train_header.addWidget(self.learn_route)
        train_layout.addLayout(train_header)

        self.learn_status = QLabel("Chọn class rồi bấm Làm mới reference để xem readiness.")
        self.learn_status.setObjectName("muted")
        self.learn_status.setWordWrap(True)
        train_layout.addWidget(self.learn_status)

        self.learn_counts = QLabel("Reviewed: -  |  Reference: -  |  Holdout: -")
        self.learn_counts.setObjectName("mono")
        self.learn_counts.setWordWrap(True)
        train_layout.addWidget(self.learn_counts)

        self.training_status = QLabel("Training: chưa có trạng thái.")
        self.training_status.setObjectName("muted")
        self.training_status.setWordWrap(True)
        train_layout.addWidget(self.training_status)

        self.candidate_path = QLabel("Candidate: -")
        self.candidate_path.setObjectName("muted")
        self.candidate_path.setWordWrap(True)
        train_layout.addWidget(self.candidate_path)

        train_actions = QHBoxLayout()
        train_actions.setSpacing(10)
        self.btn_learn_refresh = QPushButton("Làm mới reference")
        self.btn_learn_refresh.setObjectName("secondary")
        _fit_button_to_text(self.btn_learn_refresh, 145)
        self.btn_learn_refresh.clicked.connect(self._request_learn_refresh)
        train_actions.addWidget(self.btn_learn_refresh)

        self.btn_train_micro = QPushButton("Train nhanh candidate")
        self.btn_train_micro.setObjectName("primary")
        _fit_button_to_text(self.btn_train_micro, 165)
        self.btn_train_micro.clicked.connect(lambda: self._request_train_profile("micro"))
        train_actions.addWidget(self.btn_train_micro)

        self.btn_train_strong = QPushButton("Train mạnh candidate")
        self.btn_train_strong.setObjectName("secondary")
        _fit_button_to_text(self.btn_train_strong, 165)
        self.btn_train_strong.clicked.connect(lambda: self._request_train_profile("strong"))
        train_actions.addWidget(self.btn_train_strong)

        self.btn_stop_training = QPushButton("Dừng train")
        self.btn_stop_training.setObjectName("secondary")
        _fit_button_to_text(self.btn_stop_training, 105)
        self.btn_stop_training.clicked.connect(lambda: self.training_stop_requested.emit())
        train_actions.addWidget(self.btn_stop_training)

        self.btn_load_candidate = QPushButton("Load candidate để test")
        self.btn_load_candidate.setObjectName("secondary")
        _fit_button_to_text(self.btn_load_candidate, 170)
        self.btn_load_candidate.clicked.connect(self._request_candidate_load)
        train_actions.addWidget(self.btn_load_candidate)
        train_actions.addStretch()
        train_layout.addLayout(train_actions)
        train_card.setVisible(self._show_training_panel)
        outer.addWidget(train_card)

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
        self.grid.setStyleSheet(
            "QListWidget { padding: 12px; }"
            "QListWidget::item { margin: 6px; padding: 8px; }"
        )
        outer.addWidget(self.grid, 1)

        if self._show_training_panel:
            self._update_train_panel()

    def _queue_dir(self) -> Path:
        return _resolve_queue_dir(self._cfg.capture.output_dir, self._catalog_path)

    def _class_options(self) -> list[tuple[int, str]]:
        merged: dict[str, int] = {}
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

    def class_id_for_name(self, cls_name: str) -> int:
        return self._class_ids().get(cls_name, self.class_select.currentIndex())

    def selected_class_name(self) -> str:
        return self.class_select.currentText().strip()

    def request_learn_now_refresh(self) -> None:
        if not self._show_training_panel:
            return
        self._request_learn_status()
        self.training_status_requested.emit()

    def set_learn_now_status(self, status: object) -> None:
        if not self._show_training_panel:
            return
        self._learn_now_status = status if isinstance(status, dict) else {}
        self._update_train_panel()

    def set_training_status(self, status: object) -> None:
        if not self._show_training_panel:
            return
        self._training_status = status if isinstance(status, dict) else {}
        running = bool(self._training_status.get("running"))
        if running and not self._training_timer.isActive():
            self._training_timer.start()
        elif not running and self._training_timer.isActive():
            self._training_timer.stop()
        self._update_train_panel()

    def set_learn_now_action_result(self, ok: bool, message: str) -> None:
        if not self._show_training_panel:
            return
        prefix = "OK" if ok else "Lỗi"
        self.learn_status.setText(f"{prefix}: {message}")

    def load_once(self) -> None:
        if not self._loaded:
            self.reload()

    def reload(self) -> None:
        self._loaded = True
        self.grid.clear()
        qdir = self._queue_dir()
        if not qdir.exists():
            self._update_stats()
            if self._show_training_panel:
                self._request_learn_status()
            return
        files = self._display_files(qdir)
        visible_files = files[:DISPLAY_LIMIT]
        for f in visible_files:
            item = QListWidgetItem(self._icon_for_image(f), self._label_for_image(f))
            item.setData(Qt.ItemDataRole.UserRole, str(f))
            self.grid.addItem(item)
        self._prune_image_caches(visible_files)
        self._update_stats(displayed=min(len(files), DISPLAY_LIMIT))
        if self._show_training_panel:
            self._request_learn_status()

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
        trainable = int(summary.get("trainable", 0))
        needs_review = int(summary.get("needs_review", 0))
        self.stats.setText(
            f"Data hiện có: {summary['images']} ảnh, {summary['boxes']} box, "
            f"{len(classes)} nhãn. Auto: {summary['auto']}, thủ công: {summary['manual']}, "
            f"Roboflow: {summary['roboflow']}, data lạ: {summary['untrusted']}. "
            f"Trainable: {trainable}, cần duyệt: {needs_review}. "
            f"{catalog_text}. "
            f"Phân bố: {class_text}"
            + (
                f". Đang hiển thị {displayed} ảnh ưu tiên data đã duyệt/trainable; "
                "data cần duyệt vẫn xem và sửa trong Web annotate."
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
            QMessageBox.warning(self, "Thiếu nhãn", "Chọn nhãn trước khi ghi frame camera.")
            return
        self.capture_camera_sample_requested.emit(cls_name)

    def _request_camera_annotation(self) -> None:
        cls_name = self.class_select.currentText().strip()
        if not cls_name:
            QMessageBox.warning(self, "Thiếu nhãn", "Chọn nhãn trước khi chụp & gắn nhãn.")
            return
        self.camera_annotation_requested.emit(cls_name, self.class_id_for_name(cls_name))

    def _request_learn_status(self) -> None:
        if not self._show_training_panel:
            return
        self.learn_now_status_requested.emit(self.selected_class_name())

    def _request_learn_refresh(self) -> None:
        if not self._show_training_panel:
            return
        cls_name = self.selected_class_name()
        if not cls_name:
            QMessageBox.warning(self, "Thiếu nhãn", "Chọn nhãn trước khi làm mới reference.")
            return
        self.learn_now_refresh_requested.emit(cls_name)

    def _request_train_profile(self, profile: str) -> None:
        if not self._show_training_panel:
            return
        cls_name = self.selected_class_name()
        if not cls_name:
            QMessageBox.warning(self, "Thiếu nhãn", "Chọn nhãn trước khi train.")
            return
        self.learn_now_train_requested.emit(cls_name, profile)

    def _request_candidate_load(self) -> None:
        if not self._show_training_panel:
            return
        path = str(self._training_status.get("best_model_path") or "").strip()
        if not path:
            QMessageBox.warning(self, "Chưa có candidate", "Chưa có file best.pt để load test.")
            return
        self.candidate_model_test_requested.emit(path)

    def _selected_learn_now_row(self) -> dict[str, object]:
        selected = self._learn_now_status.get("selected")
        return selected if isinstance(selected, dict) else {}

    def _update_train_panel(self) -> None:
        if not self._show_training_panel:
            return
        row = self._selected_learn_now_row()
        cls_name = str(row.get("class_name") or self.selected_class_name() or "-")
        command = str(row.get("command") or "-")
        bin_index = row.get("bin_index")
        route = str(row.get("route_label") or "")
        self.learn_route.setText(f"{cls_name}: {command}/bin {bin_index or '-'} {route}".strip())

        eligible = int(row.get("eligible_reviewed_count") or 0)
        reviewed = int(row.get("reviewed_count") or 0)
        reference = int(row.get("reference_count") or 0)
        holdout = int(row.get("holdout_count") or 0)
        missing_reference = int(row.get("missing_for_reference") or 0)
        missing_micro = int(row.get("missing_for_micro_train") or 0)
        missing_strong = int(row.get("missing_for_strong_train") or 0)
        missing_holdout = int(row.get("missing_holdout_for_strong") or 0)
        issues = int(row.get("source_issue_count") or 0)
        self.learn_counts.setText(
            "Reviewed: "
            f"{reviewed} ({eligible} trainable)  |  Reference: {reference}/6"
            f"  |  Holdout: {holdout}/6  |  Source issues: {issues}"
        )

        message = str(row.get("message") or "Chưa có trạng thái Learn Now.")
        if missing_reference:
            message += f" Còn thiếu {missing_reference} mẫu để reference nhanh."
        if missing_micro:
            message += f" Còn thiếu {missing_micro} mẫu đã duyệt để train nhanh."
        elif missing_strong or missing_holdout:
            message += f" Train mạnh còn thiếu {missing_strong} mẫu train và {missing_holdout} holdout."
        self.learn_status.setText(message)

        running = bool(self._training_status.get("running"))
        training_message = str(self._training_status.get("message") or "Training đang tắt.")
        progress = float(self._training_status.get("progress_percent") or 0.0)
        run_name = str(self._training_status.get("run_name") or "")
        detail = training_message
        if run_name:
            detail += f" | run: {run_name}"
        if progress:
            detail += f" | {progress:.1f}%"
        self.training_status.setText(f"Training: {detail}")

        best_model = str(self._training_status.get("best_model_path") or "").strip()
        self.candidate_path.setText(f"Candidate: {best_model or '-'}")

        has_status = bool(row)
        self.btn_train_micro.setEnabled(
            has_status and bool(row.get("ready_for_micro_train")) and not running
        )
        self.btn_train_strong.setEnabled(
            has_status and bool(row.get("ready_for_strong_train")) and not running
        )
        self.btn_stop_training.setEnabled(running)
        self.btn_load_candidate.setEnabled(bool(best_model) and not running)

    def _capture_hard_negative(self) -> None:
        reason = str(self.hard_negative_reason_select.currentData() or "").strip()
        if not reason:
            QMessageBox.warning(self, "Thiếu loại negative", "Chọn loại negative trước khi ghi frame camera.")
            return
        self.capture_hard_negative_requested.emit(reason)

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
            f"Đánh dấu cách ly metadata cho {count} ảnh không rõ nguồn? Ảnh sẽ vẫn ở nguyên thư mục queue.",
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        moved = quarantine_untrusted_items(self._queue_dir(), catalog_path=self._catalog_path)
        self._invalidate_queue_cache()
        self.reload()
        self.counter.setText(f"Đã đánh dấu cách ly {moved} ảnh")

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
            queue_summary = summarize_queue(qdir)
            catalog_summary["trainable"] = queue_summary.get("trainable", 0)
            catalog_summary["needs_review"] = queue_summary.get("needs_review", 0)
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
                    + sources.get("manual_camera_capture", 0)
                    + sources.get("manual_web_import", 0),
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
                trust_counts = catalog.count_by_trusted()
                summary["trainable"] = trust_counts.get("trainable", 0)
                summary["needs_review"] = trust_counts.get("needs_review", 0)
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

    def _display_files(self, qdir: Path) -> list[Path]:
        key_path = qdir.resolve()
        qdir_mtime_ns = _safe_mtime_ns(qdir)
        catalog_mtime_ns = _safe_mtime_ns(self._catalog_path)
        cached = self._display_files_cache
        if (
            cached is not None
            and cached[0] == key_path
            and cached[1] == qdir_mtime_ns
            and cached[2] == catalog_mtime_ns
        ):
            return cached[3]
        files = self._catalog_display_files(qdir)
        if not files:
            files = sorted(
                qdir.glob("*.jpg"),
                key=lambda path: (_safe_mtime_ns(path), path.name),
                reverse=True,
            )[:DISPLAY_LIMIT]
        self._display_files_cache = (key_path, qdir_mtime_ns, catalog_mtime_ns, files)
        return files

    def _catalog_display_files(self, qdir: Path) -> list[Path]:
        if not self._catalog_path.exists():
            return []
        files: list[Path] = []
        seen: set[Path] = set()
        try:
            catalog = DatasetCatalog(self._catalog_path)
            try:
                for trusted in (True, False):
                    if len(files) >= DISPLAY_LIMIT:
                        break
                    rows, _total = catalog.list_items(
                        limit=DISPLAY_LIMIT - len(files),
                        trusted=trusted,
                    )
                    for row in rows:
                        path = Path(str(row.get("image_path") or ""))
                        if not path.exists():
                            continue
                        resolved = path.resolve()
                        if resolved in seen:
                            continue
                        files.append(path)
                        seen.add(resolved)
            finally:
                catalog.close()
        except Exception:
            return []
        if len(files) < DISPLAY_LIMIT and qdir.exists():
            for path in sorted(
                qdir.glob("*.jpg"),
                key=lambda item: (_safe_mtime_ns(item), item.name),
                reverse=True,
            ):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                files.append(path)
                if len(files) >= DISPLAY_LIMIT:
                    break
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
                status = _review_status_text(meta)
                source = _source_label(str(meta.get("source") or "unknown"))
                if status:
                    label = f"{status}: {label}"
                if source:
                    label = f"{label}\n{source}"
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
        self._display_files_cache = None
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
            raw_name = str(b.get("cls_name", str(cls_id)))
            cls_name = canonical_class_name(raw_name) or raw_name
            known_id = default_class_id_for_name(cls_name)
            if known_id is not None:
                cls_id = known_id
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
    trainable_classes: Counter[str] = Counter()
    blocked_classes: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    boxes = 0
    missing_meta = 0
    untrusted = 0
    needs_review = 0
    trainable = 0
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
        if _needs_review_meta(meta):
            needs_review += 1
        is_trainable = _is_trainable_meta(meta)
        if is_trainable:
            trainable += 1
        for box in meta.get("boxes") or []:
            cls_name = canonical_class_name(str(box.get("cls_name") or "")) or str(box.get("cls_name") or "?")
            boxes += 1
            classes[cls_name] += 1
            if is_trainable:
                trainable_classes[cls_name] += 1
            else:
                blocked_classes[cls_name] += 1
    return {
        "images": len(images),
        "boxes": boxes,
        "classes": classes,
        "trainable_classes": trainable_classes,
        "blocked_classes": blocked_classes,
        "auto": sources.get("auto_low_conf", 0),
        "manual": (
            sources.get("manual_import", 0)
            + sources.get("manual_camera_capture", 0)
            + sources.get("manual_web_import", 0)
        ),
        "roboflow": sum(
            count
            for source, count in sources.items()
            if source == "roboflow" or source.startswith("roboflow_")
        ),
        "unknown": sources.get("unknown", 0),
        "untrusted": untrusted,
        "needs_review": needs_review,
        "trainable": trainable,
        "missing_meta": missing_meta,
    }


def relabel_images(
    image_paths: list[Path],
    cls_name: str,
    cls_id: int,
    *,
    catalog_path: Path | None = None,
) -> int:
    changed = 0
    for img in image_paths:
        try:
            apply_dataset_review_action(
                img,
                DatasetReviewRequest(
                    action="relabel",
                    cls_name=cls_name,
                    cls_id=cls_id,
                    reason="desktop_relabel",
                    actor="desktop_admin",
                ),
                catalog_path=catalog_path,
            )
        except DatasetReviewError:
            continue
        changed += 1
    return changed


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
    marked = 0
    for img in sorted(queue_dir.glob("*.jpg")):
        meta_file = img.with_suffix(".json")
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if _is_trusted_meta(meta):
            continue
        try:
            apply_dataset_review_action(
                img,
                DatasetReviewRequest(
                    action="quarantine",
                    reason="desktop_untrusted_quarantine",
                    actor="desktop_admin",
                ),
                catalog_path=catalog_path,
            )
        except DatasetReviewError:
            continue
        marked += 1
    return marked


def _is_trusted_meta(meta: dict) -> bool:
    return classify_dataset_item(meta).state is not DatasetTrustState.QUARANTINE


def _is_trainable_meta(meta: dict) -> bool:
    return classify_dataset_item(meta).trainable


def _needs_review_meta(meta: dict) -> bool:
    return classify_dataset_item(meta).state is DatasetTrustState.NEEDS_REVIEW


def _review_status_text(meta: dict) -> str:
    decision = classify_dataset_item(meta)
    if decision.state is DatasetTrustState.HARD_NEGATIVE:
        return "Hard negative"
    if decision.state is DatasetTrustState.HOLDOUT:
        return "Holdout"
    if decision.state is DatasetTrustState.EXCLUDED:
        return "Không train"
    if decision.state is DatasetTrustState.NEEDS_REVIEW:
        return "Cần duyệt"
    if decision.state is DatasetTrustState.QUARANTINE:
        return "Data lạ"
    return ""


def _source_label(source: str) -> str:
    labels = {
        "auto_low_conf": "Auto low-conf",
        "manual_import": "Thủ công",
        "manual_camera_capture": "Camera thủ công",
        "manual_web_import": "Web thủ công",
        "hard_negative": "Hard negative",
        "roboflow": "Roboflow",
        "untrusted": "Không rõ nguồn",
        "unknown": "Không rõ nguồn",
    }
    if source.startswith("roboflow_"):
        return "Roboflow"
    if source.startswith("kaggle_"):
        return "Kaggle"
    return labels.get(source, source.replace("_", " "))


def _trusted_source_name(source: str) -> bool:
    return is_trusted_source_name(source)


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
