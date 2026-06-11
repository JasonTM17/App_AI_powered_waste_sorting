"""Manual training workflow page for reviewed class samples."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppConfig
from app.core.dataset_trust import DatasetTrustState, classify_dataset_item
from app.core.waste_categories import (
    TRAINING_CLASS_ORDER_45,
    canonical_class_name,
    default_class_id_for_name,
)
from app.ui.pages.capture import _fit_button_to_text, _resolve_queue_dir, _safe_mtime_ns
from app.utils.paths import dataset_db_path

TRAINING_GRID_LIMIT = 120


class TrainingPage(QWidget):
    open_web_requested = Signal()
    manual_phone_import_requested = Signal(str, int, object)
    capture_camera_sample_requested = Signal(str)
    camera_annotation_requested = Signal(str, int)
    capture_reviewed_camera_sample_requested = Signal(str, int, object, bool)
    learn_now_status_requested = Signal(str)
    learn_now_refresh_requested = Signal(str)
    learn_now_train_requested = Signal(str, str)
    training_stop_requested = Signal()
    training_status_requested = Signal()
    candidate_model_test_requested = Signal(str)

    def __init__(self, cfg: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self._cfg = cfg
        self._catalog_path = dataset_db_path()
        self._learn_now_status: dict[str, object] = {}
        self._training_status: dict[str, object] = {}
        self._icon_cache: dict[str, tuple[int, QIcon]] = {}
        self._loaded = False
        self._training_timer = QTimer(self)
        self._training_timer.setInterval(2500)
        self._training_timer.timeout.connect(self.training_status_requested.emit)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(16)

        title = QLabel("Huấn luyện thủ công")
        title.setObjectName("h1")
        outer.addWidget(title)

        flow_card = QFrame()
        flow_card.setObjectName("card")
        flow = QVBoxLayout(flow_card)
        flow.setContentsMargins(20, 16, 20, 16)
        flow.setSpacing(12)
        label_row = QHBoxLayout()
        label_row.setSpacing(10)
        flow.addLayout(label_row)

        label_title = QLabel("Nhãn")
        label_title.setObjectName("sectionTitle")
        label_row.addWidget(label_title)
        self.class_select = QComboBox()
        self.class_select.setEditable(True)
        self.class_select.setMinimumWidth(260)
        self.class_select.addItem("")
        for name in self._class_options():
            self.class_select.addItem(name)
        if self.class_select.lineEdit() is not None:
            self.class_select.lineEdit().setPlaceholderText("Nhập nhãn trước, ví dụ: vải")
            self.class_select.lineEdit().textChanged.connect(lambda _text: self._on_label_changed())
        self.class_select.currentTextChanged.connect(lambda _text: self._on_label_changed())
        label_row.addWidget(self.class_select)

        self.label_status = QLabel("Nhập nhãn hợp lệ trước khi thêm ảnh hoặc chụp camera.")
        self.label_status.setObjectName("muted")
        self.label_status.setWordWrap(True)
        label_row.addWidget(self.label_status, 1)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        flow.addLayout(action_row)
        self.btn_add_phone = QPushButton("Thêm ảnh thủ công")
        self.btn_add_phone.setObjectName("secondary")
        _fit_button_to_text(self.btn_add_phone, 150)
        self.btn_add_phone.clicked.connect(self._add_phone_images)
        action_row.addWidget(self.btn_add_phone)

        self.btn_capture_pending = QPushButton("Ghi frame pending")
        self.btn_capture_pending.setObjectName("secondary")
        _fit_button_to_text(self.btn_capture_pending, 145)
        self.btn_capture_pending.clicked.connect(self._capture_camera_sample)
        action_row.addWidget(self.btn_capture_pending)

        self.btn_annotate = QPushButton("Chụp & gắn nhãn")
        self.btn_annotate.setObjectName("primary")
        _fit_button_to_text(self.btn_annotate, 145)
        self.btn_annotate.clicked.connect(self._request_camera_annotation)
        action_row.addWidget(self.btn_annotate)

        self.btn_open_web = QPushButton("Mở Web annotate")
        self.btn_open_web.setObjectName("secondary")
        _fit_button_to_text(self.btn_open_web, 140)
        self.btn_open_web.clicked.connect(self.open_web_requested.emit)
        action_row.addWidget(self.btn_open_web)
        action_row.addStretch()
        outer.addWidget(flow_card)

        train_card = QFrame()
        train_card.setObjectName("card")
        train = QVBoxLayout(train_card)
        train.setContentsMargins(20, 16, 20, 16)
        train.setSpacing(10)
        header = QHBoxLayout()
        header.setSpacing(10)
        section = QLabel("Candidate model")
        section.setObjectName("sectionTitle")
        header.addWidget(section)
        header.addStretch()
        self.learn_route = QLabel("Route: -")
        self.learn_route.setObjectName("mono")
        header.addWidget(self.learn_route)
        train.addLayout(header)

        self.learn_status = QLabel("Chọn nhãn rồi bấm Làm mới reference để xem readiness.")
        self.learn_status.setObjectName("muted")
        self.learn_status.setWordWrap(True)
        train.addWidget(self.learn_status)
        self.learn_counts = QLabel("Reviewed: -  |  Reference: -  |  Holdout: -")
        self.learn_counts.setObjectName("mono")
        self.learn_counts.setWordWrap(True)
        train.addWidget(self.learn_counts)
        self.training_status = QLabel("Training: chưa có trạng thái.")
        self.training_status.setObjectName("muted")
        self.training_status.setWordWrap(True)
        train.addWidget(self.training_status)
        self.candidate_path = QLabel("Candidate: -")
        self.candidate_path.setObjectName("muted")
        self.candidate_path.setWordWrap(True)
        train.addWidget(self.candidate_path)

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
        self.btn_stop_training.clicked.connect(self.training_stop_requested.emit)
        train_actions.addWidget(self.btn_stop_training)

        self.btn_load_candidate = QPushButton("Load candidate để test")
        self.btn_load_candidate.setObjectName("secondary")
        _fit_button_to_text(self.btn_load_candidate, 170)
        self.btn_load_candidate.clicked.connect(self._request_candidate_load)
        train_actions.addWidget(self.btn_load_candidate)
        train_actions.addStretch()
        train.addLayout(train_actions)
        outer.addWidget(train_card)

        self.stats = QLabel("")
        self.stats.setObjectName("muted")
        self.stats.setWordWrap(True)
        outer.addWidget(self.stats)

        self.grid = QListWidget()
        self.grid.setObjectName("card")
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setIconSize(QSize(160, 120))
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.grid.setSpacing(12)
        self.grid.setUniformItemSizes(True)
        self.grid.setStyleSheet(
            "QListWidget { padding: 12px; }"
            "QListWidget::item { margin: 6px; padding: 8px; }"
        )
        outer.addWidget(self.grid, 1)

        self._on_label_changed()

    def _class_options(self) -> list[str]:
        names = list(TRAINING_CLASS_ORDER_45)
        for mapping in self._cfg.mappings:
            canonical = canonical_class_name(mapping.class_name)
            if canonical and default_class_id_for_name(canonical) is not None and canonical not in names:
                names.append(canonical)
        return names

    def _queue_dir(self) -> Path:
        return _resolve_queue_dir(self._cfg.capture.output_dir, self._catalog_path)

    def _label_target(self) -> tuple[str, str, int | None]:
        raw = self.class_select.currentText().strip()
        canonical = canonical_class_name(raw)
        cls_id = default_class_id_for_name(canonical)
        return raw, canonical, cls_id

    def selected_class_name(self) -> str:
        _raw, canonical, _cls_id = self._label_target()
        return canonical

    def class_id_for_name(self, cls_name: str) -> int:
        canonical = canonical_class_name(cls_name)
        cls_id = default_class_id_for_name(canonical)
        return int(cls_id if cls_id is not None else 0)

    def request_learn_now_refresh(self) -> None:
        if self._valid_label():
            self._request_learn_status()
        self.training_status_requested.emit()

    def set_learn_now_status(self, status: object) -> None:
        self._learn_now_status = status if isinstance(status, dict) else {}
        self._update_train_panel()

    def set_training_status(self, status: object) -> None:
        self._training_status = status if isinstance(status, dict) else {}
        running = bool(self._training_status.get("running"))
        if running and not self._training_timer.isActive():
            self._training_timer.start()
        elif not running and self._training_timer.isActive():
            self._training_timer.stop()
        self._update_train_panel()

    def set_learn_now_action_result(self, ok: bool, message: str) -> None:
        prefix = "OK" if ok else "Lỗi"
        self.learn_status.setText(f"{prefix}: {message}")
        self.reload()

    def load_once(self) -> None:
        if not self._loaded:
            self.reload()

    def reload(self) -> None:
        self._loaded = True
        self.grid.clear()
        raw, canonical, cls_id = self._label_target()
        if not raw or cls_id is None:
            self.stats.setText("Nhập nhãn hợp lệ để xem mẫu huấn luyện của class đó.")
            return
        qdir = self._queue_dir()
        files = self._selected_class_files(qdir, canonical) if qdir.exists() else []
        for image_path in files[:TRAINING_GRID_LIMIT]:
            item = QListWidgetItem(self._icon_for_image(image_path), self._label_for_image(image_path))
            item.setData(Qt.ItemDataRole.UserRole, str(image_path))
            self.grid.addItem(item)
        self._update_local_stats(qdir, canonical, len(files))
        self._request_learn_status()

    def _valid_label(self) -> bool:
        _raw, canonical, cls_id = self._label_target()
        return bool(canonical and cls_id is not None)

    def _on_label_changed(self) -> None:
        raw, canonical, cls_id = self._label_target()
        valid = bool(raw and canonical and cls_id is not None)
        if not raw:
            self.label_status.setText("Nhập nhãn hợp lệ trước khi thêm ảnh hoặc chụp camera.")
        elif valid:
            suffix = f"{raw} → {canonical}" if raw.casefold() != canonical.casefold() else canonical
            self.label_status.setText(f"Nhãn hợp lệ: {suffix} (id {cls_id}).")
        else:
            self.label_status.setText(f"Không tìm thấy class hợp lệ cho nhãn: {raw}")
        for button in (
            self.btn_add_phone,
            self.btn_capture_pending,
            self.btn_annotate,
            self.btn_learn_refresh,
        ):
            button.setEnabled(valid)
        self._update_train_panel()

    def _add_phone_images(self) -> None:
        _raw, canonical, cls_id = self._label_target()
        if cls_id is None:
            QMessageBox.warning(self, "Thiếu nhãn", "Nhập nhãn hợp lệ trước khi thêm ảnh.")
            return
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn ảnh thủ công",
            "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp)",
        )
        if not files:
            return
        self.manual_phone_import_requested.emit(canonical, int(cls_id), list(files))

    def _capture_camera_sample(self) -> None:
        _raw, canonical, cls_id = self._label_target()
        if cls_id is None:
            QMessageBox.warning(self, "Thiếu nhãn", "Nhập nhãn hợp lệ trước khi ghi frame.")
            return
        self.capture_camera_sample_requested.emit(canonical)

    def _request_camera_annotation(self) -> None:
        _raw, canonical, cls_id = self._label_target()
        if cls_id is None:
            QMessageBox.warning(self, "Thiếu nhãn", "Nhập nhãn hợp lệ trước khi chụp & gắn nhãn.")
            return
        self.camera_annotation_requested.emit(canonical, int(cls_id))

    def _request_learn_status(self) -> None:
        _raw, canonical, cls_id = self._label_target()
        if cls_id is not None:
            self.learn_now_status_requested.emit(canonical)

    def _request_learn_refresh(self) -> None:
        _raw, canonical, cls_id = self._label_target()
        if cls_id is None:
            QMessageBox.warning(self, "Thiếu nhãn", "Nhập nhãn hợp lệ trước khi làm mới reference.")
            return
        self.learn_now_refresh_requested.emit(canonical)

    def _request_train_profile(self, profile: str) -> None:
        _raw, canonical, cls_id = self._label_target()
        if cls_id is None:
            QMessageBox.warning(self, "Thiếu nhãn", "Nhập nhãn hợp lệ trước khi train.")
            return
        self.learn_now_train_requested.emit(canonical, profile)

    def _request_candidate_load(self) -> None:
        path = str(self._training_status.get("best_model_path") or "").strip()
        if not path:
            QMessageBox.warning(self, "Chưa có candidate", "Chưa có file best.pt để load test.")
            return
        self.candidate_model_test_requested.emit(path)

    def _selected_learn_now_row(self) -> dict[str, object]:
        selected = self._learn_now_status.get("selected")
        return selected if isinstance(selected, dict) else {}

    def _update_train_panel(self) -> None:
        row = self._selected_learn_now_row()
        raw, canonical, cls_id = self._label_target()
        display_name = str(row.get("class_name") or canonical or raw or "-")
        command = str(row.get("command") or "-")
        bin_index = row.get("bin_index")
        route = str(row.get("route_label") or "")
        self.learn_route.setText(f"{display_name}: {command}/bin {bin_index or '-'} {route}".strip())

        eligible = int(row.get("eligible_reviewed_count") or 0)
        reviewed = int(row.get("reviewed_count") or 0)
        reference = int(row.get("reference_count") or 0)
        holdout = int(row.get("holdout_count") or 0)
        issues = int(row.get("source_issue_count") or 0)
        self.learn_counts.setText(
            f"Reviewed: {reviewed} ({eligible} trainable)  |  Reference: {reference}/6"
            f"  |  Holdout: {holdout}/6  |  Source issues: {issues}"
        )

        message = str(row.get("message") or "Chưa có trạng thái Learn Now.")
        missing_reference = int(row.get("missing_for_reference") or 0)
        missing_micro = int(row.get("missing_for_micro_train") or 0)
        missing_strong = int(row.get("missing_for_strong_train") or 0)
        missing_holdout = int(row.get("missing_holdout_for_strong") or 0)
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
        valid = cls_id is not None
        self.btn_train_micro.setEnabled(
            valid and has_status and bool(row.get("ready_for_micro_train")) and not running
        )
        self.btn_train_strong.setEnabled(
            valid and has_status and bool(row.get("ready_for_strong_train")) and not running
        )
        self.btn_stop_training.setEnabled(running)
        self.btn_load_candidate.setEnabled(bool(best_model) and not running)

    def _selected_class_files(self, qdir: Path, class_name: str) -> list[Path]:
        files: list[Path] = []
        for image_path in sorted(qdir.glob("*.jpg"), key=_safe_mtime_ns, reverse=True):
            meta = _read_meta(image_path)
            if _meta_has_class(meta, class_name):
                files.append(image_path)
        return files

    def _update_local_stats(self, qdir: Path, class_name: str, total: int) -> None:
        counts: Counter[str] = Counter()
        if qdir.exists():
            for image_path in qdir.glob("*.jpg"):
                meta = _read_meta(image_path)
                if not _meta_has_class(meta, class_name):
                    continue
                decision = classify_dataset_item(meta)
                counts[decision.state.value] += 1
        self.stats.setText(
            f"{class_name}: {total} ảnh trong queue. "
            f"Đã duyệt/trainable: {counts[DatasetTrustState.TRAINABLE.value]}, "
            f"cần duyệt: {counts[DatasetTrustState.NEEDS_REVIEW.value]}, "
            f"holdout: {counts[DatasetTrustState.HOLDOUT.value]}, "
            f"bị loại/cách ly: {counts[DatasetTrustState.EXCLUDED.value] + counts[DatasetTrustState.QUARANTINE.value]}."
        )

    def _label_for_image(self, image_path: Path) -> str:
        meta = _read_meta(image_path)
        label = image_path.stem[:8]
        boxes = meta.get("boxes") if isinstance(meta, dict) else None
        if isinstance(boxes, list) and boxes:
            box = boxes[0]
            label = f"{box.get('cls_name', '?')} {float(box.get('conf', 0) or 0):.2f}"
        if isinstance(meta, dict):
            status = _status_label(meta)
            source = str(meta.get("source") or "unknown").replace("_", " ")
            if status:
                label = f"{status}: {label}"
            label = f"{label}\n{source}"
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


def _read_meta(image_path: Path) -> dict[str, object]:
    try:
        meta = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
    except Exception:
        return {}
    return meta if isinstance(meta, dict) else {}


def _meta_has_class(meta: dict[str, object], class_name: str) -> bool:
    boxes = meta.get("boxes")
    if not isinstance(boxes, list):
        return False
    wanted = canonical_class_name(class_name)
    return any(
        canonical_class_name(str(box.get("cls_name") or "")) == wanted
        for box in boxes
        if isinstance(box, dict)
    )


def _status_label(meta: dict[str, object]) -> str:
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
