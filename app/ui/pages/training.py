"""Manual training workflow page for reviewed class samples."""

from __future__ import annotations

import json
import time
from collections import Counter
from contextlib import suppress
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
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
from app.core.dataset_catalog import DatasetCatalog
from app.core.dataset_trust import DatasetTrustState, classify_dataset_item
from app.core.waste_categories import (
    TRAINING_CLASS_ORDER_45,
    canonical_class_name,
    default_class_id_for_name,
)
from app.ui.pages.capture import _fit_button_to_text, _resolve_queue_dir, _safe_mtime_ns
from app.ui.widgets.flow_layout import FlowLayout
from app.ui.widgets.safe_inputs import SafeComboBox
from app.utils.logging import logger
from app.utils.paths import dataset_db_path

TRAINING_GRID_LIMIT = 80
THUMBNAIL_BATCH_SIZE = 10


class _TrainingDataWorker(QThread):
    metadata_ready = Signal(int, object)
    thumbnails_ready = Signal(int, object)
    failed = Signal(int, str)

    def __init__(
        self,
        request_id: int,
        catalog_path: Path,
        queue_dir: Path,
        class_name: str,
    ) -> None:
        super().__init__()
        self._request_id = request_id
        self._catalog_path = catalog_path
        self._queue_dir = queue_dir
        self._class_name = class_name

    def run(self) -> None:
        started = time.perf_counter()
        try:
            payload = self._load_catalog_payload()
            self.metadata_ready.emit(self._request_id, payload)
            logger.info(
                "training catalog ready class={} rows={} total={} elapsed_ms={:.0f}",
                self._class_name,
                len(payload["rows"]),
                payload["total"],
                (time.perf_counter() - started) * 1000,
            )
            self._decode_thumbnails(payload["rows"])
            self._repair_catalog_if_needed(payload)
        except Exception as exc:
            logger.exception("training data load failed class={}", self._class_name)
            self.failed.emit(self._request_id, str(exc))

    def _load_catalog_payload(self) -> dict[str, object]:
        catalog = DatasetCatalog(self._catalog_path)
        try:
            rows, total = catalog.list_items_for_box_class(
                self._class_name,
                limit=TRAINING_GRID_LIMIT,
            )
            counts = catalog.count_trust_states_for_box_class(self._class_name)
            catalog_total = catalog.count_total()
        finally:
            catalog.close()
        for row in rows:
            row["selected_cls_name"] = self._class_name
        if catalog_total > 0:
            return {
                "rows": rows,
                "total": total,
                "counts": counts,
                "source": "catalog",
                "catalog_total": catalog_total,
            }

        rows, total, counts = self._fallback_scan()
        return {
            "rows": rows,
            "total": total,
            "counts": counts,
            "source": "fallback",
            "catalog_total": catalog_total,
        }

    def _repair_catalog_if_needed(self, payload: dict[str, object]) -> None:
        if self.isInterruptionRequested() or not self._queue_dir.exists():
            return
        queue_total = sum(1 for _ in self._queue_dir.glob("*.jpg"))
        catalog_total = int(payload.get("catalog_total") or 0)
        if queue_total == catalog_total:
            return
        logger.warning(
            "training catalog mismatch queue={} catalog={}; re-indexing in background",
            queue_total,
            catalog_total,
        )
        catalog = DatasetCatalog(self._catalog_path)
        try:
            catalog.index_queue(self._queue_dir)
        finally:
            catalog.close()
        if self.isInterruptionRequested():
            return
        refreshed = self._load_catalog_payload()
        self.metadata_ready.emit(self._request_id, refreshed)
        self._decode_thumbnails(refreshed["rows"])

    def _fallback_scan(self) -> tuple[list[dict[str, object]], int, dict[str, int]]:
        rows: list[dict[str, object]] = []
        counts: Counter[str] = Counter()
        total = 0
        if not self._queue_dir.exists():
            return rows, total, dict(counts)
        for image_path in sorted(
            self._queue_dir.glob("*.jpg"),
            key=_safe_mtime_ns,
            reverse=True,
        ):
            if self.isInterruptionRequested():
                break
            meta = _read_meta(image_path)
            if not _meta_has_class(meta, self._class_name):
                continue
            total += 1
            decision = classify_dataset_item(meta)
            counts[decision.state.value] += 1
            if len(rows) < TRAINING_GRID_LIMIT:
                rows.append(
                    {
                        "image_path": str(image_path.resolve()),
                        "source": str(meta.get("source") or "unknown"),
                        "trust_state": decision.state.value,
                        "cls_name": self._class_name,
                    }
                )
        return rows, total, dict(counts)

    def _decode_thumbnails(self, rows: list[dict[str, object]]) -> None:
        batch: list[tuple[str, QImage]] = []
        started = time.perf_counter()
        decoded = 0
        for row in rows:
            if self.isInterruptionRequested():
                break
            path = str(row.get("image_path") or "")
            image = QImage(path)
            if image.isNull():
                continue
            image = image.scaled(
                160,
                120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            batch.append((path, image))
            decoded += 1
            if len(batch) >= THUMBNAIL_BATCH_SIZE:
                self.thumbnails_ready.emit(self._request_id, batch)
                batch = []
        if batch:
            self.thumbnails_ready.emit(self._request_id, batch)
        logger.info(
            "training thumbnails decoded class={} count={} elapsed_ms={:.0f}",
            self._class_name,
            decoded,
            (time.perf_counter() - started) * 1000,
        )


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
        self._load_request_id = 0
        self._load_workers: list[_TrainingDataWorker] = []
        self._grid_items: dict[str, QListWidgetItem] = {}
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(160)
        self._reload_timer.timeout.connect(self.reload)
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
        label_row = FlowLayout(margin=0, h_spacing=10, v_spacing=10)
        flow.addLayout(label_row)

        label_title = QLabel("Nhãn")
        label_title.setObjectName("sectionTitle")
        label_row.addWidget(label_title)
        self.class_select = SafeComboBox()
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
        label_row.addWidget(self.label_status)

        action_row = FlowLayout(margin=0, h_spacing=10, v_spacing=10)
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

        train_actions = FlowLayout(margin=0, h_spacing=10, v_spacing=10)
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

        pen_idx = self.class_select.findText("Pen")
        if pen_idx >= 0:
            self.class_select.setCurrentIndex(pen_idx)
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
        started = time.perf_counter()
        self._loaded = True
        for previous in self._load_workers:
            previous.requestInterruption()
        self._load_request_id += 1
        request_id = self._load_request_id
        self.grid.clear()
        self._grid_items.clear()
        raw, canonical, cls_id = self._label_target()
        if not raw or cls_id is None:
            self.stats.setText("Nhập nhãn hợp lệ để xem mẫu huấn luyện của class đó.")
            return
        qdir = self._queue_dir()
        self.stats.setText(f"Đang tải mẫu {canonical} từ catalog...")
        worker = _TrainingDataWorker(
            request_id,
            self._catalog_path,
            qdir,
            canonical,
        )
        worker.metadata_ready.connect(self._on_training_metadata_ready)
        worker.thumbnails_ready.connect(self._on_training_thumbnails_ready)
        worker.failed.connect(self._on_training_load_failed)
        worker.finished.connect(lambda worker=worker: self._forget_load_worker(worker))
        worker.finished.connect(worker.deleteLater)
        self._load_workers.append(worker)
        worker.start()
        self._request_learn_status()
        logger.info(
            "training page scheduled class={} request={} elapsed_ms={:.1f}",
            canonical,
            request_id,
            (time.perf_counter() - started) * 1000,
        )

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
        if self._loaded:
            self._load_request_id += 1
            self.stats.setText(f"Đang chuẩn bị tải mẫu {canonical or raw}...")
            self._reload_timer.start()

    def _on_training_metadata_ready(self, request_id: int, payload: object) -> None:
        if request_id != self._load_request_id or not isinstance(payload, dict):
            return
        rows = payload.get("rows")
        rows = rows if isinstance(rows, list) else []
        self.grid.clear()
        self._grid_items.clear()
        for row in rows:
            if not isinstance(row, dict):
                continue
            path = str(row.get("image_path") or "")
            item = QListWidgetItem(self._label_for_catalog_row(row))
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.grid.addItem(item)
            self._grid_items[path] = item
        raw, canonical, _cls_id = self._label_target()
        class_name = canonical or raw
        total = int(payload.get("total") or 0)
        counts = payload.get("counts")
        counts = counts if isinstance(counts, dict) else {}
        excluded = int(counts.get(DatasetTrustState.EXCLUDED.value, 0)) + int(
            counts.get(DatasetTrustState.QUARANTINE.value, 0)
        )
        self.stats.setText(
            f"{class_name}: {total} ảnh trong queue. "
            f"Đã duyệt/trainable: {int(counts.get(DatasetTrustState.TRAINABLE.value, 0))}, "
            f"cần duyệt: {int(counts.get(DatasetTrustState.NEEDS_REVIEW.value, 0))}, "
            f"holdout: {int(counts.get(DatasetTrustState.HOLDOUT.value, 0))}, "
            f"bị loại/cách ly: {excluded}."
        )

    def _on_training_thumbnails_ready(self, request_id: int, batch: object) -> None:
        if request_id != self._load_request_id or not isinstance(batch, list):
            return
        for path, image in batch:
            item = self._grid_items.get(str(path))
            if item is not None and isinstance(image, QImage):
                item.setIcon(QIcon(QPixmap.fromImage(image)))

    def _on_training_load_failed(self, request_id: int, message: str) -> None:
        if request_id == self._load_request_id:
            self.stats.setText(f"Không tải được dữ liệu huấn luyện: {message}")

    def _forget_load_worker(self, worker: _TrainingDataWorker) -> None:
        with suppress(ValueError):
            self._load_workers.remove(worker)

    @staticmethod
    def _label_for_catalog_row(row: dict[str, object]) -> str:
        class_name = str(row.get("selected_cls_name") or row.get("cls_name") or "?")
        trust_state = str(row.get("trust_state") or "")
        source = str(row.get("source") or "unknown").replace("_", " ")
        status = trust_state.replace("_", " ")
        return f"{status}: {class_name}\n{source}" if status else f"{class_name}\n{source}"

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
            Qt.TransformationMode.FastTransformation,
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
