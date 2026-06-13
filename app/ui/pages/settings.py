"""Settings tab: camera/model/uart/app sections with Test buttons."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppConfig
from app.core.hardware_profile import (
    GD5800_RX_PIN,
    GD5800_STARTUP_TRACK,
    GD5800_TX_PIN,
    PROFILE_ID,
    PROXIMITY_SENSORS,
    ROUTES,
    SERVO_WAIT_POSITIONS,
)
from app.ui.pages.settings_audio_section import AudioSettingsSection
from app.ui.widgets.safe_inputs import SafeComboBox, SafeSpinBox
from app.utils.camera_source import normalize_camera_source
from app.utils.paths import resource_path


def _icon(name: str) -> QIcon:
    path = resource_path(f"app/ui/resources/icons/{name}.svg")
    return QIcon(str(path)) if path.exists() else QIcon()


def _button_icon(button: QPushButton, name: str) -> None:
    button.setIcon(_icon(name))
    button.setIconSize(QSize(18, 18))


def _auto_hardware_scan_enabled() -> bool:
    return QGuiApplication.platformName().lower() != "offscreen"


class _CameraScan(QThread):
    """Probe camera indices 0..max_idx across all Windows backends.

    Returns labels like "1 (DSHOW) USB Camera". When PnP enumeration
    succeeds, each working OpenCV index is annotated with the friendly
    device name and a tag — so user can tell the laptop webcam apart
    from a real plugged-in USB camera.
    """

    done = Signal(object)

    def __init__(self, max_idx: int = 9):
        super().__init__()
        self._max = max_idx

    def run(self):
        import cv2

        from app.utils.camera_enum import list_directshow_cameras, list_pnp_cameras

        pnp = list_pnp_cameras()
        externals = [c for c in pnp if c.get("is_external")]
        builtins = [c for c in pnp if c.get("is_usb") and not c.get("is_external")]
        dshow_names = list_directshow_cameras()

        backends = [
            ("DSHOW", cv2.CAP_DSHOW),
            ("MSMF", cv2.CAP_MSMF),
            ("ANY", cv2.CAP_ANY),
        ]
        seen: set[int] = set()
        rows: list[tuple[int, dict]] = []
        for name, b in backends:
            for i in range(self._max + 1):
                if i in seen:
                    continue
                cap = cv2.VideoCapture(i, b)
                ok = cap.isOpened()
                if ok:
                    ok2, frame = cap.read()
                    if ok2 and frame is not None:
                        friendly = ""
                        if name == "DSHOW" and i < len(dshow_names):
                            friendly = dshow_names[i]
                        lname = friendly.lower()
                        if "obs" in lname or "virtual" in lname:
                            tag = "Camera ảo"
                            prio = 8
                        elif any(c.get("name") == friendly for c in externals):
                            tag = "USB"
                            prio = 0
                        elif any(c.get("name") == friendly for c in builtins):
                            tag = "Webcam laptop"
                            prio = 9
                        elif externals and i == 0 and not builtins:
                            tag = "USB"
                            prio = 0
                        elif builtins and i == 0:
                            tag = "Webcam laptop"
                            prio = 9
                        else:
                            tag = "Camera"
                            prio = 5
                        h, w = frame.shape[:2]
                        label_parts = [f"{i} ({name})", tag]
                        if friendly:
                            label_parts.append(friendly[:48])
                        label_parts.append(f"{w}x{h}")
                        rows.append(
                            (
                                prio,
                                {
                                    "source": f"{i} ({name})",
                                    "label": " - ".join(label_parts),
                                    "tag": tag,
                                    "backend": name,
                                },
                            )
                        )
                        seen.add(i)
                cap.release()
        rows.sort()
        self.done.emit({"rows": [r[1] for r in rows], "devices": pnp})


class _PortScan(QThread):
    """List visible COM ports off the GUI thread."""

    done = Signal(list)

    def run(self):
        from app.utils.serial_enum import list_serial_ports
        self.done.emit(list_serial_ports())


def _section(title: str) -> tuple[QFrame, QFormLayout]:
    box = QFrame()
    box.setObjectName("card")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(22, 18, 22, 18)
    layout.setSpacing(14)
    h = QLabel(title)
    h.setObjectName("section-title")
    layout.addWidget(h)
    form = QFormLayout()
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    form.setHorizontalSpacing(18)
    form.setVerticalSpacing(12)
    layout.addLayout(form)
    return box, form


class SettingsPage(QWidget):
    config_saved = Signal(AppConfig)
    test_camera_requested = Signal(str)
    test_uart_requested = Signal(str, int)
    test_hardware_requested = Signal(str, int, str)
    test_voice_requested = Signal(str, str, str)
    speaker_output_mode_changed = Signal(str)
    speaker_voice_gender_changed = Signal(str)
    actuation_test_mode_changed = Signal(bool)
    reload_model_requested = Signal(str)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self._cfg = cfg.model_copy(deep=True)

        page = QVBoxLayout(self)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(0)

        body = QWidget()
        outer = QVBoxLayout(body)
        outer.setContentsMargins(24, 20, 24, 28)
        outer.setSpacing(16)

        title = QLabel("Cài đặt")
        title.setObjectName("h1")
        outer.addWidget(title)

        # camera
        cam_box, cam_form = _section("Camera")
        self.cam_source = SafeComboBox()
        self.cam_source.setEditable(False)
        initial_source = self._cfg.camera.source.strip()
        if normalize_camera_source(initial_source) == "0":
            initial_source = ""
        self._preferred_camera_source = initial_source
        self.cam_source.addItem("Đang kiểm tra camera USB...", "")
        self.cam_source.setCurrentIndex(0)
        self.cam_hint = QLabel("Bấm Scan để tìm camera USB đang cắm vào máy.")
        self.cam_hint.setWordWrap(True)
        self.cam_hint.setObjectName("muted")
        self.cam_w = SafeSpinBox()
        self.cam_w.setRange(160, 7680)
        self.cam_w.setValue(self._cfg.camera.width)
        self.cam_h = SafeSpinBox()
        self.cam_h.setRange(120, 4320)
        self.cam_h.setValue(self._cfg.camera.height)
        self.cam_mirror = QCheckBox("Lật ngang")
        self.cam_mirror.setChecked(self._cfg.camera.mirror)
        self.cam_rotation = SafeComboBox()
        for label, value in [
            ("0 độ - mốc ban đầu", 0),
            ("90 độ phải", 90),
            ("180 độ", 180),
            ("90 độ trái", 270),
        ]:
            self.cam_rotation.addItem(label, value)
        rotation_idx = self.cam_rotation.findData(self._cfg.camera.rotation)
        self.cam_rotation.setCurrentIndex(max(rotation_idx, 0))
        cam_form.addRow("Nguồn", self.cam_source)
        cam_form.addRow("Thiết bị", self.cam_hint)
        cam_form.addRow("Chiều rộng", self.cam_w)
        cam_form.addRow("Chiều cao", self.cam_h)
        cam_form.addRow("", self.cam_mirror)
        cam_form.addRow("Xoay", self.cam_rotation)
        cam_btns = QHBoxLayout()
        btn_scan_cam = QPushButton("Quét camera")
        btn_scan_cam.setObjectName("secondary")
        _button_icon(btn_scan_cam, "camera")
        btn_scan_cam.clicked.connect(self._scan_cameras)
        self.btn_test_cam = QPushButton("Test camera")
        self.btn_test_cam.setObjectName("secondary")
        _button_icon(self.btn_test_cam, "play")
        self.btn_test_cam.setEnabled(False)
        self.btn_test_cam.clicked.connect(
            lambda: self.test_camera_requested.emit(self._current_camera_source())
        )
        cam_btns.addWidget(btn_scan_cam)
        cam_btns.addWidget(self.btn_test_cam)
        cam_btns.addStretch()
        cam_btns_w = QWidget()
        cam_btns_w.setLayout(cam_btns)
        cam_form.addRow("", cam_btns_w)
        outer.addWidget(cam_box)
        self._cam_scan: _CameraScan | None = None
        self._camera_scan_started = False

        roi_box, roi_form = _section("ROI vùng khay")
        self.roi_enabled = QCheckBox("Bật ROI cho lệnh dò từ camera")
        self.roi_enabled.setChecked(self._cfg.roi.enabled)
        self.roi_x = SafeSpinBox()
        self.roi_x.setRange(0, 7680)
        self.roi_x.setValue(self._cfg.roi.x)
        self.roi_y = SafeSpinBox()
        self.roi_y.setRange(0, 4320)
        self.roi_y.setValue(self._cfg.roi.y)
        self.roi_w = SafeSpinBox()
        self.roi_w.setRange(0, 7680)
        self.roi_w.setValue(self._cfg.roi.width)
        self.roi_h = SafeSpinBox()
        self.roi_h.setRange(0, 4320)
        self.roi_h.setValue(self._cfg.roi.height)
        self.roi_hint = QLabel(
            "Bật ROI và đặt vùng khay trước khi bật chế độ test cơ cấu. "
            "Nếu ROI tắt hoặc rỗng, camera vẫn hiện box nhưng không gửi UART."
        )
        self.roi_hint.setWordWrap(True)
        self.roi_hint.setObjectName("muted")
        roi_form.addRow("", self.roi_enabled)
        roi_form.addRow("X", self.roi_x)
        roi_form.addRow("Y", self.roi_y)
        roi_form.addRow("Chiều rộng", self.roi_w)
        roi_form.addRow("Chiều cao", self.roi_h)
        roi_form.addRow("Ghi chú", self.roi_hint)
        outer.addWidget(roi_box)

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
        self.mdl_device = SafeComboBox()
        self.mdl_device.addItems(["auto", "cpu", "cuda"])
        self.mdl_device.setCurrentText(self._cfg.model.device)
        self.mdl_conf = QSlider(Qt.Orientation.Horizontal)
        self.mdl_conf.setRange(0, 100)
        self.mdl_conf.setValue(int(self._cfg.model.conf_threshold * 100))
        self.mdl_conf_label = QLabel(f"{self._cfg.model.conf_threshold:.2f}")
        self.mdl_conf_label.setObjectName("mono")
        self.mdl_conf.valueChanged.connect(lambda v: self.mdl_conf_label.setText(f"{v / 100:.2f}"))
        conf_row = QHBoxLayout()
        conf_row.addWidget(self.mdl_conf)
        conf_row.addWidget(self.mdl_conf_label)
        conf_w = QWidget()
        conf_w.setLayout(conf_row)
        self.mdl_iou = QSlider(Qt.Orientation.Horizontal)
        self.mdl_iou.setRange(0, 100)
        self.mdl_iou.setValue(int(self._cfg.model.iou_threshold * 100))
        self.mdl_imgsz = SafeComboBox()
        self.mdl_imgsz.addItems(["320", "480", "640", "800", "960"])
        self.mdl_imgsz.setCurrentText(str(self._cfg.model.input_size))
        mdl_form.addRow("File", path_w)
        mdl_form.addRow("Device", self.mdl_device)
        mdl_form.addRow("Confidence", conf_w)
        mdl_form.addRow("IoU", self.mdl_iou)
        mdl_form.addRow("Input size", self.mdl_imgsz)
        btn_reload = QPushButton("Tải lại model")
        btn_reload.setObjectName("secondary")
        _button_icon(btn_reload, "play")
        btn_reload.clicked.connect(lambda: self.reload_model_requested.emit(self.mdl_path.text()))
        mdl_form.addRow("", btn_reload)
        outer.addWidget(mdl_box)

        # uart
        uart_box, uart_form = _section("UART")
        self.uart_port = SafeComboBox()
        self.uart_port.setEditable(False)
        if self._cfg.uart.port.strip():
            self.uart_port.addItem(self._cfg.uart.port, self._cfg.uart.port)
            self.uart_port.setCurrentText(self._cfg.uart.port)
        else:
            self.uart_port.addItem("Đang kiểm tra cổng USB/Arduino...", "")
        self.uart_hint = QLabel("Ưu tiên cổng USB/Arduino. Bluetooth COM sẽ không được chọn tự động.")
        self.uart_hint.setWordWrap(True)
        self.uart_hint.setObjectName("muted")
        self.uart_baud = SafeComboBox()
        self.uart_baud.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.uart_baud.setCurrentText(str(self._cfg.uart.baud))
        self.uart_auto = QCheckBox("Tự kết nối lại")
        self.uart_auto.setChecked(self._cfg.uart.auto_reconnect)
        self.uart_timeout = SafeSpinBox()
        self.uart_timeout.setRange(50, 5000)
        self.uart_timeout.setSuffix(" ms")
        self.uart_timeout.setValue(self._cfg.uart.ack_timeout_ms)
        self.uart_protocol = SafeComboBox()
        self.uart_protocol.addItem("Block: hữu cơ / vô cơ / tái chế", "plain_group")
        self.uart_protocol.addItem("Firmware: SORT:O/R/I", "sort_line")
        idx_protocol = self.uart_protocol.findData(self._cfg.uart.protocol)
        self.uart_protocol.setCurrentIndex(idx_protocol if idx_protocol >= 0 else 0)
        uart_form.addRow("Port", self.uart_port)
        uart_form.addRow("Thiết bị", self.uart_hint)
        uart_form.addRow("Baud", self.uart_baud)
        uart_form.addRow("Ack timeout", self.uart_timeout)
        uart_form.addRow("Protocol", self.uart_protocol)
        uart_form.addRow("", self.uart_auto)
        uart_btns = QHBoxLayout()
        btn_scan_uart = QPushButton("Quét cổng")
        btn_scan_uart.setObjectName("secondary")
        _button_icon(btn_scan_uart, "hardware")
        btn_scan_uart.clicked.connect(self._scan_ports)
        self.btn_test_uart = QPushButton("Test ping")
        self.btn_test_uart.setObjectName("secondary")
        _button_icon(self.btn_test_uart, "play")
        self.btn_test_uart.clicked.connect(
            lambda: self.test_uart_requested.emit(
                self._current_uart_port(),
                int(self.uart_baud.currentText())
            )
        )
        uart_btns.addWidget(btn_scan_uart)
        uart_btns.addWidget(self.btn_test_uart)
        uart_btns.addStretch()
        uart_btns_w = QWidget()
        uart_btns_w.setLayout(uart_btns)
        uart_form.addRow("", uart_btns_w)
        outer.addWidget(uart_box)
        self._port_scan: _PortScan | None = None
        # populate port list immediately on first show so user sees real ports
        if _auto_hardware_scan_enabled():
            QTimer.singleShot(0, self._scan_ports)

        hw_box, hw_form = _section("Mapping phần cứng")
        hw_form.addRow("Profile", QLabel(PROFILE_ID))
        hw_form.addRow(
            "GD5800",
            QLabel(f"Startup track {GD5800_STARTUP_TRACK}; TX {GD5800_TX_PIN}; RX {GD5800_RX_PIN}"),
        )
        wait = ", ".join(f"{pin}={angle}" for pin, angle in SERVO_WAIT_POSITIONS.items())
        hw_form.addRow("Servo wait", QLabel(wait))
        for pins in PROXIMITY_SENSORS:
            hw_form.addRow(
                f"Tiệm cận {pins.label}",
                QLabel(f"pin {pins.pin}, active {pins.active_level}, track {pins.gd5800_track}"),
            )
        for route in ROUTES:
            row = QHBoxLayout()
            positions = ", ".join(
                f"{pin}={angle}" for pin, angle in route.servo_positions.items()
            )
            display_label = _route_display_label(route.label)
            row.addWidget(
                QLabel(
                    f"{display_label}: {route.command} -> {route.serial_payload}\\n -> "
                    f"thùng {route.bin_index}, servo {route.servo_pin} ({positions}), "
                    f"track {route.gd5800_track}"
                )
            )
            btn = QPushButton(f"Test {display_label}")
            btn.setObjectName("secondary")
            btn.clicked.connect(
                lambda _checked=False, cmd=route.command: self.test_hardware_requested.emit(
                    self._current_uart_port(),
                    int(self.uart_baud.currentText()),
                    cmd,
                )
            )
            row.addWidget(btn)
            row.addStretch()
            row_w = QWidget()
            row_w.setLayout(row)
            hw_form.addRow("", row_w)
        self.uart_test_result = QLabel("Chưa test phần cứng.")
        self.uart_test_result.setWordWrap(True)
        self.uart_test_result.setObjectName("muted")
        hw_form.addRow("Kết quả", self.uart_test_result)
        self.actuation_mode = QCheckBox("Bật phân loại tự động")
        self.actuation_mode_hint = QLabel(
            "Đang tắt. Bật camera và chờ UART sẵn sàng trước khi bật tự động."
        )
        self.actuation_mode_hint.setWordWrap(True)
        self.actuation_mode_hint.setObjectName("muted")
        self.actuation_mode.toggled.connect(self._on_actuation_mode_toggled)
        hw_form.addRow("", self.actuation_mode)
        hw_form.addRow("Camera E2E", self.actuation_mode_hint)
        outer.addWidget(hw_box)

        audio_box, audio_form = _section("Âm thanh")
        self.audio_section = AudioSettingsSection(self._cfg)
        self.audio_section.voice_test_requested.connect(self.test_voice_requested.emit)
        self.audio_section.output_mode_changed.connect(self.speaker_output_mode_changed.emit)
        self.audio_section.voice_gender_changed.connect(self.speaker_voice_gender_changed.emit)
        self.speaker_cooldown = self.audio_section.speaker_cooldown
        audio_form.addRow(self.audio_section)
        outer.addWidget(audio_box)

        # app
        app_box, app_form = _section("Ứng dụng")
        self.theme_select = SafeComboBox()
        self.theme_select.addItems(["dark", "light"])
        self.theme_select.setCurrentText(self._cfg.theme)
        self.lang_select = SafeComboBox()
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

        page.addWidget(body)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if _auto_hardware_scan_enabled() and not self._camera_scan_started:
            self._camera_scan_started = True
            QTimer.singleShot(0, self._scan_cameras)

    def _browse_model(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select model", "", "PyTorch (*.pt)")
        if f:
            self.mdl_path.setText(f)

    def _scan_ports(self):
        if self._port_scan is not None and self._port_scan.isRunning():
            return
        scan = _PortScan()
        self._port_scan = scan

        def _apply(ports: list[dict]):
            current = self._current_uart_port()
            usb_ports = [p for p in ports if p.get("is_usb")]
            self.uart_port.blockSignals(True)
            self.uart_port.clear()
            if not ports:
                self.uart_port.addItem("Chưa thấy cổng USB/Arduino", "")
                self.uart_hint.setText("Chưa thấy cổng COM nào. Cắm Arduino/ESP32 bằng USB rồi bấm Scan cổng.")
                self.btn_test_uart.setEnabled(False)
            elif usb_ports:
                for p in usb_ports:
                    label = f"{p['device']} (USB) {p.get('name','')[:40]}"
                    self.uart_port.addItem(label, p["device"])
                idx = self.uart_port.findData(current)
                self.uart_port.setCurrentIndex(idx if idx >= 0 else 0)
                self.uart_hint.setText("Đã tìm thấy cổng USB/Arduino. Chọn đúng cổng rồi bấm Test ping.")
                self.btn_test_uart.setEnabled(True)
            else:
                self.uart_port.addItem("Chưa thấy cổng USB/Arduino", "")
                for p in ports:
                    label = f"{p['device']} (Bluetooth/khác) {p.get('name','')[:40]}"
                    self.uart_port.addItem(label, p["device"])
                self.uart_port.setCurrentIndex(0)
                self.uart_hint.setText("Chỉ thấy COM Bluetooth/khác. Cắm Arduino/ESP32 bằng USB rồi Scan lại.")
                self.btn_test_uart.setEnabled(False)
            self.uart_port.blockSignals(False)

        scan.done.connect(_apply)
        scan.finished.connect(scan.deleteLater)
        scan.start()

    def _scan_cameras(self):
        if self._cam_scan is not None and self._cam_scan.isRunning():
            return
        self.cam_hint.setText("Đang quét camera...")
        scan = _CameraScan(max_idx=9)
        self._cam_scan = scan

        def _apply(payload):
            all_rows = payload.get("rows", []) if isinstance(payload, dict) else []
            devices = payload.get("devices", []) if isinstance(payload, dict) else []
            usb_rows = [r for r in all_rows if r.get("tag") == "USB"]
            rows = usb_rows
            current = self._preferred_camera_source or self._current_camera_source()
            self.cam_source.blockSignals(True)
            self.cam_source.clear()
            if rows:
                for row in rows:
                    self.cam_source.addItem(row["label"], row["source"])
                idx = self._find_camera_source(current)
                if idx >= 0:
                    self.cam_source.setCurrentIndex(idx)
                else:
                    self.cam_source.setCurrentIndex(0)
            else:
                self.cam_source.addItem("Chưa có camera USB", "")
                self.cam_source.setCurrentIndex(0)
            self.btn_test_cam.setEnabled(bool(rows))
            self.cam_source.blockSignals(False)
            usb_devices = [d for d in devices if d.get("is_external")]
            if usb_rows:
                self.cam_hint.setText(
                    "Đã tìm thấy camera USB đọc được frame. Chọn dòng USB rồi bấm Test camera."
                )
            elif usb_devices:
                names = ", ".join(d.get("name", "USB Camera") for d in usb_devices)
                self.cam_hint.setText(
                    f"Windows thấy {names}, nhưng OpenCV chưa đọc được frame. "
                    "Đóng app khác đang dùng camera, rút/cắm lại USB, rồi Scan lại."
                )
            elif all_rows:
                self.cam_hint.setText("Chỉ sử dụng camera USB, nên đã ẩn webcam laptop/camera ảo.")
            else:
                self.cam_hint.setText("Chưa tìm thấy camera đọc được frame.")

        scan.done.connect(_apply)
        scan.finished.connect(scan.deleteLater)
        scan.start()

    def _find_camera_source(self, source: str) -> int:
        normalized = normalize_camera_source(source)
        for i in range(self.cam_source.count()):
            data = self.cam_source.itemData(i)
            if data is not None and normalize_camera_source(data) == normalized:
                return i
            if normalize_camera_source(self.cam_source.itemText(i)) == normalized:
                return i
        return -1

    def _current_camera_source(self) -> str:
        text = self.cam_source.currentText().strip()
        idx = self.cam_source.currentIndex()
        data = self.cam_source.itemData(idx) if idx >= 0 else None
        if data is not None and text == self.cam_source.itemText(idx).strip():
            return str(data).strip()
        return normalize_camera_source(text)

    def _current_uart_port(self) -> str:
        idx = self.uart_port.currentIndex()
        data = self.uart_port.itemData(idx) if idx >= 0 else None
        if data is not None:
            return str(data).strip()
        return self.uart_port.currentText().split(" ")[0].strip()

    def _collect(self) -> AppConfig:
        cfg = self._cfg.model_copy(deep=True)
        cfg.camera.source = self._current_camera_source()
        cfg.camera.width = self.cam_w.value()
        cfg.camera.height = self.cam_h.value()
        cfg.camera.mirror = self.cam_mirror.isChecked()
        cfg.camera.rotation = int(self.cam_rotation.currentData() or 0)
        cfg.roi.enabled = self.roi_enabled.isChecked()
        cfg.roi.x = self.roi_x.value()
        cfg.roi.y = self.roi_y.value()
        cfg.roi.width = self.roi_w.value()
        cfg.roi.height = self.roi_h.value()
        cfg.model.path = self.mdl_path.text()
        cfg.model.device = self.mdl_device.currentText()
        cfg.model.conf_threshold = self.mdl_conf.value() / 100
        cfg.model.iou_threshold = self.mdl_iou.value() / 100
        cfg.model.input_size = int(self.mdl_imgsz.currentText())
        cfg.uart.port = self._current_uart_port()
        cfg.uart.baud = int(self.uart_baud.currentText())
        cfg.uart.ack_timeout_ms = self.uart_timeout.value()
        cfg.uart.auto_reconnect = self.uart_auto.isChecked()
        cfg.uart.protocol = self.uart_protocol.currentData() or "plain_group"
        audio_output_mode = self.audio_section.output_mode()
        if audio_output_mode not in {"hardware", "computer_speaker"}:
            audio_output_mode = "hardware"
        cfg.speaker.output_mode = audio_output_mode
        cfg.speaker.enabled = audio_output_mode == "computer_speaker"
        cfg.speaker.voice_gender = self.audio_section.voice_gender()
        cfg.speaker.cooldown_seconds = float(self.speaker_cooldown.value())
        cfg.theme = self.theme_select.currentText()
        cfg.language = self.lang_select.currentText()
        cfg.minimize_to_tray = self.tray_check.isChecked()
        cfg.autostart = self.autostart_check.isChecked()
        return cfg

    def _save(self):
        self.config_saved.emit(self._collect())

    def set_uart_test_result(self, ok: bool, message: str) -> None:
        prefix = "OK" if ok else "LỖI"
        self.uart_test_result.setText(f"{prefix}: {message}")

    def set_actuation_test_mode(self, enabled: bool) -> None:
        self.actuation_mode.blockSignals(True)
        self.actuation_mode.setChecked(enabled)
        self.actuation_mode.blockSignals(False)
        self._set_actuation_mode_hint(enabled)

    def _on_actuation_mode_toggled(self, enabled: bool) -> None:
        self._set_actuation_mode_hint(enabled)
        self.actuation_test_mode_changed.emit(enabled)

    def _set_actuation_mode_hint(self, enabled: bool) -> None:
        text = (
            "Đang bật. Mỗi vật hợp lệ trong ROI sẽ tự nhận diện, phát âm thanh, "
            "đổ đúng ngăn và chờ khay trống trước lượt tiếp theo."
            if enabled
            else "Đang tắt. Bật camera và chờ UART sẵn sàng trước khi bật tự động."
        )
        self.actuation_mode_hint.setText(text)

    def _reset(self):
        self._cfg = self._cfg.model_copy(deep=True)


def _route_display_label(label: str) -> str:
    return {
        "Huu co": "Hữu cơ",
        "Vo co": "Vô cơ",
        "Tai che": "Tái chế",
    }.get(label, label)
