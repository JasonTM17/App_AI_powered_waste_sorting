"""Settings tab: camera/model/uart/app sections with Test buttons."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppConfig


class _CameraScan(QThread):
    """Probe camera indices 0..max_idx across all Windows backends.

    Returns labels like "0 (MSMF)", "1 (DSHOW)" so user can tell which
    backend each index responds on.
    """

    done = Signal(list)

    def __init__(self, max_idx: int = 9):
        super().__init__()
        self._max = max_idx

    def run(self):
        import cv2
        backends = [
            ("MSMF", cv2.CAP_MSMF),
            ("DSHOW", cv2.CAP_DSHOW),
            ("ANY", cv2.CAP_ANY),
        ]
        seen: set[int] = set()
        found: list[str] = []
        for name, b in backends:
            for i in range(self._max + 1):
                if i in seen:
                    continue
                cap = cv2.VideoCapture(i, b)
                ok = cap.isOpened()
                if ok:
                    ok2, frame = cap.read()
                    if ok2 and frame is not None:
                        found.append(f"{i} ({name})")
                        seen.add(i)
                cap.release()
        self.done.emit(found)


def _section(title: str) -> tuple[QFrame, QFormLayout]:
    box = QFrame()
    box.setObjectName("card")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(20, 16, 20, 16)
    layout.setSpacing(12)
    h = QLabel(title)
    h.setStyleSheet("font-size: 16px; font-weight: 700;")
    layout.addWidget(h)
    form = QFormLayout()
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(10)
    layout.addLayout(form)
    return box, form


class SettingsPage(QWidget):
    config_saved = Signal(AppConfig)
    test_camera_requested = Signal(str)
    test_uart_requested = Signal(str, int)
    reload_model_requested = Signal(str)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self._cfg = cfg.model_copy(deep=True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(16)

        title = QLabel("Cài đặt")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        outer.addWidget(title)

        # camera
        cam_box, cam_form = _section("Camera")
        self.cam_source = QComboBox()
        self.cam_source.setEditable(True)
        self.cam_source.addItems(["0", "1", "2"])
        self.cam_source.setCurrentText(self._cfg.camera.source)
        self.cam_w = QSpinBox()
        self.cam_w.setRange(160, 7680)
        self.cam_w.setValue(self._cfg.camera.width)
        self.cam_h = QSpinBox()
        self.cam_h.setRange(120, 4320)
        self.cam_h.setValue(self._cfg.camera.height)
        self.cam_mirror = QCheckBox("Lật ngang")
        self.cam_mirror.setChecked(self._cfg.camera.mirror)
        cam_form.addRow("Nguồn", self.cam_source)
        cam_form.addRow("Width", self.cam_w)
        cam_form.addRow("Height", self.cam_h)
        cam_form.addRow("", self.cam_mirror)
        cam_btns = QHBoxLayout()
        btn_scan_cam = QPushButton("⟳ Scan")
        btn_scan_cam.setObjectName("secondary")
        btn_scan_cam.clicked.connect(self._scan_cameras)
        btn_test_cam = QPushButton("▶ Test camera")
        btn_test_cam.setObjectName("secondary")
        btn_test_cam.clicked.connect(
            lambda: self.test_camera_requested.emit(self.cam_source.currentText())
        )
        cam_btns.addWidget(btn_scan_cam)
        cam_btns.addWidget(btn_test_cam)
        cam_btns.addStretch()
        cam_btns_w = QWidget()
        cam_btns_w.setLayout(cam_btns)
        cam_form.addRow("", cam_btns_w)
        outer.addWidget(cam_box)
        self._cam_scan: _CameraScan | None = None

        # model
        mdl_box, mdl_form = _section("Model AI")
        self.mdl_path = QLineEdit(str(self._cfg.model.path))
        btn_browse = QPushButton("Browse…")
        btn_browse.setObjectName("secondary")
        btn_browse.clicked.connect(self._browse_model)
        path_row = QHBoxLayout()
        path_row.addWidget(self.mdl_path)
        path_row.addWidget(btn_browse)
        path_w = QWidget()
        path_w.setLayout(path_row)
        self.mdl_device = QComboBox()
        self.mdl_device.addItems(["cpu", "cuda"])
        self.mdl_device.setCurrentText(self._cfg.model.device)
        self.mdl_conf = QSlider(Qt.Orientation.Horizontal)
        self.mdl_conf.setRange(0, 100)
        self.mdl_conf.setValue(int(self._cfg.model.conf_threshold * 100))
        self.mdl_conf_label = QLabel(f"{self._cfg.model.conf_threshold:.2f}")
        self.mdl_conf.valueChanged.connect(lambda v: self.mdl_conf_label.setText(f"{v / 100:.2f}"))
        conf_row = QHBoxLayout()
        conf_row.addWidget(self.mdl_conf)
        conf_row.addWidget(self.mdl_conf_label)
        conf_w = QWidget()
        conf_w.setLayout(conf_row)
        self.mdl_iou = QSlider(Qt.Orientation.Horizontal)
        self.mdl_iou.setRange(0, 100)
        self.mdl_iou.setValue(int(self._cfg.model.iou_threshold * 100))
        self.mdl_imgsz = QComboBox()
        self.mdl_imgsz.addItems(["320", "480", "640", "800", "960"])
        self.mdl_imgsz.setCurrentText(str(self._cfg.model.input_size))
        mdl_form.addRow("File", path_w)
        mdl_form.addRow("Device", self.mdl_device)
        mdl_form.addRow("Confidence", conf_w)
        mdl_form.addRow("IoU", self.mdl_iou)
        mdl_form.addRow("Input size", self.mdl_imgsz)
        btn_reload = QPushButton("↻ Hot reload model")
        btn_reload.setObjectName("secondary")
        btn_reload.clicked.connect(lambda: self.reload_model_requested.emit(self.mdl_path.text()))
        mdl_form.addRow("", btn_reload)
        outer.addWidget(mdl_box)

        # uart
        uart_box, uart_form = _section("UART")
        self.uart_port = QLineEdit(self._cfg.uart.port)
        self.uart_baud = QComboBox()
        self.uart_baud.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.uart_baud.setCurrentText(str(self._cfg.uart.baud))
        self.uart_auto = QCheckBox("Auto reconnect")
        self.uart_auto.setChecked(self._cfg.uart.auto_reconnect)
        self.uart_timeout = QSpinBox()
        self.uart_timeout.setRange(50, 5000)
        self.uart_timeout.setSuffix(" ms")
        self.uart_timeout.setValue(self._cfg.uart.ack_timeout_ms)
        uart_form.addRow("Port", self.uart_port)
        uart_form.addRow("Baud", self.uart_baud)
        uart_form.addRow("Ack timeout", self.uart_timeout)
        uart_form.addRow("", self.uart_auto)
        btn_test_uart = QPushButton("▶ Test ping")
        btn_test_uart.setObjectName("secondary")
        btn_test_uart.clicked.connect(
            lambda: self.test_uart_requested.emit(
                self.uart_port.text(), int(self.uart_baud.currentText())
            )
        )
        uart_form.addRow("", btn_test_uart)
        outer.addWidget(uart_box)

        # app
        app_box, app_form = _section("Ứng dụng")
        self.theme_select = QComboBox()
        self.theme_select.addItems(["dark", "light"])
        self.theme_select.setCurrentText(self._cfg.theme)
        self.lang_select = QComboBox()
        self.lang_select.addItems(["vi", "en"])
        self.lang_select.setCurrentText(self._cfg.language)
        self.tray_check = QCheckBox("Minimize ra system tray")
        self.tray_check.setChecked(self._cfg.minimize_to_tray)
        self.autostart_check = QCheckBox("Khởi động cùng Windows")
        self.autostart_check.setChecked(self._cfg.autostart)
        app_form.addRow("Theme", self.theme_select)
        app_form.addRow("Ngôn ngữ", self.lang_select)
        app_form.addRow("", self.tray_check)
        app_form.addRow("", self.autostart_check)
        outer.addWidget(app_box)

        outer.addStretch()

        save_row = QHBoxLayout()
        save_row.addStretch()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setObjectName("secondary")
        btn_save = QPushButton("Lưu cài đặt")
        btn_save.setObjectName("primary")
        btn_cancel.clicked.connect(self._reset)
        btn_save.clicked.connect(self._save)
        save_row.addWidget(btn_cancel)
        save_row.addWidget(btn_save)
        outer.addLayout(save_row)

    def _browse_model(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select model", "", "PyTorch (*.pt)")
        if f:
            self.mdl_path.setText(f)

    def _scan_cameras(self):
        if self._cam_scan is not None and self._cam_scan.isRunning():
            return
        scan = _CameraScan(max_idx=9)
        self._cam_scan = scan

        def _apply(found: list[str]):
            current = self.cam_source.currentText()
            self.cam_source.blockSignals(True)
            self.cam_source.clear()
            items = found if found else ["0"]
            self.cam_source.addItems(items)
            # If user already typed an index/url, keep it in front
            if current and current not in items:
                self.cam_source.insertItem(0, current)
                self.cam_source.setCurrentText(current)
            else:
                self.cam_source.setCurrentText(items[0])
            self.cam_source.blockSignals(False)

        scan.done.connect(_apply)
        scan.finished.connect(scan.deleteLater)
        scan.start()

    def _collect(self) -> AppConfig:
        cfg = self._cfg.model_copy(deep=True)
        cfg.camera.source = self.cam_source.currentText().split(" ")[0].strip()
        cfg.camera.width = self.cam_w.value()
        cfg.camera.height = self.cam_h.value()
        cfg.camera.mirror = self.cam_mirror.isChecked()
        cfg.model.path = self.mdl_path.text()
        cfg.model.device = self.mdl_device.currentText()
        cfg.model.conf_threshold = self.mdl_conf.value() / 100
        cfg.model.iou_threshold = self.mdl_iou.value() / 100
        cfg.model.input_size = int(self.mdl_imgsz.currentText())
        cfg.uart.port = self.uart_port.text()
        cfg.uart.baud = int(self.uart_baud.currentText())
        cfg.uart.ack_timeout_ms = self.uart_timeout.value()
        cfg.uart.auto_reconnect = self.uart_auto.isChecked()
        cfg.theme = self.theme_select.currentText()
        cfg.language = self.lang_select.currentText()
        cfg.minimize_to_tray = self.tray_check.isChecked()
        cfg.autostart = self.autostart_check.isChecked()
        return cfg

    def _save(self):
        self.config_saved.emit(self._collect())

    def _reset(self):
        self._cfg = self._cfg.model_copy(deep=True)
