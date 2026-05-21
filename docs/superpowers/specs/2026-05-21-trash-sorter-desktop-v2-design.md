# Trash Sorter Desktop v2 — Design Spec

- **Date**: 2026-05-21
- **Owner**: Nguyen Tien Son
- **Status**: Draft (pending user review)
- **Supersedes**: legacy bundled `PHAN LOAI RAC.exe` (PyInstaller frozen build)

## 1. Mục tiêu

Viết lại sạch ứng dụng phân loại rác desktop hiện có, giữ nguyên model YOLO `best.pt`, thay thế GUI và backend logic bằng codebase modular, dễ maintain, dễ mở rộng sang web ở phase 2.

### 1.1. Yêu cầu chức năng

1. Đọc camera (USB hoặc IP) thời gian thực, FPS ≥ 30 trên i5 + CPU.
2. Suy luận YOLO trên model `best.pt` đã có, threshold + IoU + input size cấu hình được.
3. Vẽ bbox + label + confidence lên video feed.
4. Tracking object qua các frame (ByteTrack) — 1 vật thể = 1 lệnh UART duy nhất.
5. Gửi lệnh UART text-line tới board điều khiển; nhận ack; auto-reconnect khi mất.
6. Lưu lịch sử detection (timestamp, class, conf, ảnh thumbnail, ack status) vào SQLite cục bộ.
7. UI 5 tab: Live, Lịch sử, Mapping, Capture, Cài đặt.
8. Dark mode mặc định, light mode tuỳ chọn, font Inter, frameless custom title bar.
9. Hot-reload model `.pt` không cần restart app.
10. Capture frame có conf thấp ra folder review để re-train.

### 1.2. Non-goals (phase 1)

- Multi-camera đồng thời (chỉ 1 camera).
- Multi-UART đồng thời (chỉ 1 board).
- Cloud sync, web online (phase 2 spec riêng).
- Auto-update binary qua mạng (phase sau).
- iOS/macOS native (chỉ Windows + Linux dev).

### 1.3. Success criteria

- End-to-end latency (camera → UART) ≤ 80 ms median trên i5 CPU only.
- App không bao giờ crash do unplug camera/UART/board giữa runtime.
- Coverage `core/` ≥ 80% lines, `ui/` ≥ 50%.
- Cold start ≤ 4s trên SSD.
- 1000 detection liên tục không leak RAM (RSS tăng ≤ 50MB).
- User chưa từng dùng cũng tự cấu hình được camera + UART trong < 2 phút.

## 2. Kiến trúc tổng thể

### 2.1. Sơ đồ luồng

```
Camera (OpenCV)
   │ frames (BGR ndarray)
   ▼
Frame Queue (maxsize=2, drop oldest)
   │
   ▼
InferenceWorker (QThread)
   │ raw boxes (xyxy, conf, cls)
   ▼
Filter (conf, ROI)
   │
   ▼
Tracker (ByteTrack)
   │ stable detections w/ track_id
   ▼
Decision: track_id new && stable_frames ≥ N ?
   │ yes → emit detection_event(track_id, cls, conf, frame)
   │
   ├──► GUI                  (signal/slot, append to live log)
   ├──► HistoryService       (SQLite insert async)
   └──► UartWorker           (encode SORT:<cmd>:<conf>\n, write, await ack)
                                │
                                ▼
                         ack_event(track_id, status)
                                │
                                ▼
                         HistoryService.update_status
```

### 2.2. Module boundaries

`core/` không bao giờ import `ui/`. Phase 2 web sẽ import `core/` qua HTTP wrapper.

| Module | Trách nhiệm | Public API |
|---|---|---|
| `core.config` | Load/save/validate config từ JSON | `Config.load()`, `Config.save()`, pydantic models |
| `core.camera` | Đọc camera, emit frame qua signal | `CameraWorker(source).frame_ready` |
| `core.inference` | Wrap YOLO `best.pt`, infer trên frame, trả Detection list | `InferenceEngine.predict(frame) -> List[Detection]` |
| `core.tracker` | ByteTrack wrapper, gán track_id | `Tracker.update(detections) -> List[TrackedDetection]` |
| `core.uart` | pyserial wrapper, queue + ack + reconnect | `UartWorker.send(command)`, `ack_received` |
| `core.history` | SQLite CRUD, schema migration, export | `HistoryService.insert/query/export_csv()` |
| `core.events` | Dataclass cho detection, ack, error events | `Detection`, `TrackedDetection`, `AckEvent` |
| `ui.main_window` | Shell: sidebar + content + status bar + title bar | — |
| `ui.pages.*` | 5 tab độc lập, mỗi cái 1 file | — |
| `ui.widgets.*` | Reusable: VideoView, StatCard, Toast, Skeleton | — |

### 2.3. Threading model

- **Main thread (Qt event loop)**: chỉ UI render và signal/slot routing.
- **CameraWorker**: QThread, blocking `cap.read()`, push vào queue.
- **InferenceWorker**: QThread, pop frame, infer, emit detection.
- **UartWorker**: QThread, pop command queue, write, đợi ack với timeout.
- **HistoryService**: chạy trong main thread nhưng dùng `aiosqlite` qua `qasync`, hoặc đơn giản hơn: queue + 1 worker thread riêng, vì DB latency thấp.

Communication giữa thread chỉ qua **Qt signal/slot** (thread-safe) — không bao giờ truy cập widget từ worker.

### 2.4. Cấu trúc thư mục

```
trash-sorter-v2/
├── app/
│   ├── __main__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── camera.py
│   │   ├── inference.py
│   │   ├── tracker.py
│   │   ├── uart.py
│   │   ├── history.py
│   │   └── events.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py
│   │   ├── pages/
│   │   │   ├── live.py
│   │   │   ├── history.py
│   │   │   ├── mapping.py
│   │   │   ├── capture.py
│   │   │   └── settings.py
│   │   ├── widgets/
│   │   │   ├── video_view.py
│   │   │   ├── stat_card.py
│   │   │   ├── toast.py
│   │   │   ├── skeleton.py
│   │   │   └── title_bar.py
│   │   └── resources/
│   │       ├── icons/
│   │       ├── qss/
│   │       │   ├── dark.qss
│   │       │   └── light.qss
│   │       └── i18n/
│   │           ├── vi.qm
│   │           └── en.qm
│   └── utils/
│       ├── logging.py
│       └── paths.py
├── firmware/
│   └── arduino_servo/
│       └── arduino_servo.ino
├── models/
│   └── best.pt
├── tests/
│   ├── unit/
│   ├── integration/
│   └── ui/
├── docs/
│   ├── adr/
│   │   ├── template.md
│   │   ├── 0001-record-architecture-decisions.md
│   │   ├── 0002-pyside6-over-pyqt5.md
│   │   ├── 0003-bytetrack-for-tracking.md
│   │   └── 0004-uart-text-protocol.md
│   └── superpowers/specs/
├── scripts/
│   ├── inspect_model.py
│   └── build_exe.py
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env.example
├── README.md
├── CHANGELOG.md
└── config.json
```

## 3. Domain models

### 3.1. Config schema (pydantic v2)

```python
class CameraConfig(BaseModel):
    source: str = "0"           # "0", "1", hoặc URL "rtsp://..."
    width: int = 1280
    height: int = 720
    mirror: bool = False

class ModelConfig(BaseModel):
    path: Path = Path("models/best.pt")
    device: Literal["cpu", "cuda"] = "cpu"
    conf_threshold: float = Field(0.4, ge=0.0, le=1.0)
    iou_threshold: float = Field(0.45, ge=0.0, le=1.0)
    input_size: int = 640
    half_precision: bool = False

class UartConfig(BaseModel):
    port: str = "COM3"
    baud: int = 9600
    auto_reconnect: bool = True
    ack_timeout_ms: int = 200

class ClassMapping(BaseModel):
    class_name: str             # "plastic"
    command: str                # "S"
    bin_index: int              # 2
    enabled: bool = True

class RoiConfig(BaseModel):
    enabled: bool = False
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

class CaptureConfig(BaseModel):
    mode: Literal["off", "manual", "auto_low_conf"] = "auto_low_conf"
    low_conf_threshold: float = 0.6
    output_dir: Path = Path("dataset_v2")

class AppConfig(BaseModel):
    camera: CameraConfig
    model: ModelConfig
    uart: UartConfig
    mappings: list[ClassMapping]
    roi: RoiConfig
    capture: CaptureConfig
    theme: Literal["dark", "light"] = "dark"
    language: Literal["vi", "en"] = "vi"
    minimize_to_tray: bool = True
    autostart: bool = False
```

Config lưu tại `%APPDATA%/TrashSorter/config.json` trên Windows, `~/.config/trash-sorter/config.json` trên Linux. File ban đầu được seed từ template `config.example.json` của repo.

### 3.2. Event/data classes

```python
@dataclass(frozen=True)
class Detection:
    cls_id: int
    cls_name: str
    conf: float
    xyxy: tuple[int, int, int, int]   # absolute pixel

@dataclass(frozen=True)
class TrackedDetection:
    track_id: int
    detection: Detection
    stable_frames: int
    first_seen_ts: float

@dataclass(frozen=True)
class DetectionEvent:
    track_id: int
    cls_id: int
    cls_name: str
    conf: float
    frame: np.ndarray             # BGR copy at moment of decision
    ts: datetime

@dataclass(frozen=True)
class AckEvent:
    track_id: int
    command: str
    status: Literal["ok", "no_ack", "error"]
    rtt_ms: int | None
```

### 3.3. SQLite schema

```sql
CREATE TABLE detections (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id      INTEGER NOT NULL,
    ts            TEXT NOT NULL,        -- ISO8601 UTC
    cls_id        INTEGER NOT NULL,
    cls_name      TEXT NOT NULL,
    conf          REAL NOT NULL,
    bbox_x1       INTEGER, bbox_y1 INTEGER,
    bbox_x2       INTEGER, bbox_y2 INTEGER,
    thumbnail     BLOB,                  -- JPEG, max 100x75
    uart_command  TEXT,
    ack_status    TEXT,                  -- ok | no_ack | error | pending
    rtt_ms        INTEGER
);
CREATE INDEX idx_detections_ts ON detections(ts);
CREATE INDEX idx_detections_cls ON detections(cls_name);

CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
INSERT INTO schema_version VALUES (1);
```

Migration framework đơn giản: file `app/core/migrations/00X_*.sql`, chạy tuần tự theo `version` < target.

## 4. UART protocol

### 4.1. Wire format

App → board (text-line, UTF-8, terminator `\n`):

```
SORT:<command>:<conf2digits>\n
PING\n
```

- `<command>` là 1 ký tự A–Z, ánh xạ từ class qua `ClassMapping.command`.
- `<conf2digits>` ví dụ `0.92` (2 chữ số sau dấu chấm).

Board → app:

```
ACK:<command>\n         # đã xử lý xong (servo về home)
NACK:<command>:<reason>\n
PONG\n
LOG:<text>\n            # debug, app log INFO
```

### 4.2. Lifecycle

1. App connect cổng → gửi `PING\n`, đợi `PONG\n` ≤ 1s. Pass = status xanh.
2. Mỗi detection event → enqueue command, FIFO.
3. Worker pop command → `write(SORT:S:0.92\n)`, start timer 200ms (configurable).
4. Nhận `ACK:S\n` trước timeout → `status=ok`, đo `rtt_ms`.
5. Timeout không có ack → `status=no_ack`, **không retry** (tránh kẹt servo).
6. Disconnect detect (write fail / serial exception) → worker đóng port, marker đỏ trên status bar, retry connect mỗi 2s.
7. Queue command tối đa 100 entries trong RAM khi disconnected; vượt → drop oldest.

### 4.3. Test loopback

`tests/integration/test_uart_loopback.py` dùng virtual COM pair (com0com trên Windows, `socat` trên Linux): TX socket → RX socket. Test full lifecycle gồm timeout giả lập (không respond) và happy path.

## 5. Error handling

| Lớp | Lỗi | Phát hiện | Hành vi |
|---|---|---|---|
| Camera | `cap.read()` trả `False` 5 frame liên tiếp | CameraWorker | Đóng cap, retry mở 3 lần × 1s, status đỏ, toast "Mất camera". GUI overlay "RECONNECTING…" trên last frame. |
| Camera | Exception OpenCV | try/except trong worker | Log + emit `error_signal`, retry như trên. |
| Model | File không tồn tại lúc startup | `core.inference.load()` | Modal blocker yêu cầu chọn `.pt` khác hoặc Quit. |
| Model | OOM CUDA | Exception | Tự động fallback CPU + toast cảnh báo + cập nhật config. |
| Model | Inference fail 1 frame | try/except | Log warning, skip frame. Loop tiếp. |
| UART | Port không tồn tại | `serial.Serial()` exception | Status đỏ, toast, không block app. Auto-reconnect khi `auto_reconnect=true`. |
| UART | Write timeout | pyserial timeout | Đóng port, mark dead, reconnect. |
| UART | Ack timeout | Custom timer | Mark `no_ack` trong history. Tiếp tục command kế. |
| DB | SQLite locked | Exception trong worker | Retry 3 lần × 50ms. Vẫn fail → ghi JSONL fallback `%APPDATA%/TrashSorter/fallback.log`. |
| DB | Disk full | OSError | Toast lỗi, switch sang fallback log, status bar warning. |
| Config | File hỏng JSON / schema sai | `pydantic.ValidationError` | Modal "Config hỏng, dùng default?" → backup file cũ thành `.broken`, ghi default mới. |

**Nguyên tắc**: detection loop không bao giờ exit do I/O. Lỗi ở bất kỳ subsystem chỉ degrade graceful + status visible + toast.

**Logging**: structured JSON ra `%APPDATA%/TrashSorter/logs/app-YYYY-MM-DD.log`, rotate 7 ngày qua `loguru`. Field: `ts, level, module, event, track_id, class, conf, latency_ms, error`.

## 6. Performance

| Metric | Target | Cách đạt |
|---|---|---|
| End-to-end latency (cam→UART) | ≤ 80 ms median | Skip-frame khi queue đầy; YOLO infer thread riêng |
| GUI FPS render | ≥ 30 | `QImage.fromData` zero-copy; bbox vẽ trong `paintEvent`, không re-create QPixmap mỗi frame |
| Inference latency | ≤ 50 ms (CPU i5) | Input size 640; YOLOv8n hoặc nhỏ hơn; FP16 nếu GPU |
| RAM | ≤ 1.5 GB | Frame queue maxsize=2; history pagination 200 row/trang; thumbnail JPEG ≤ 100×75 |
| CPU (no GPU) | ≤ 60% i5 4-core | Cap target FPS infer = 15 nếu user không cần > 15 |
| Cold start | ≤ 4s | Lazy import `torch`/`ultralytics`; splash 1.5s che cảm giác chờ |

## 7. UI/UX

### 7.1. Design tokens

```
background:    #0B1220
surface:       #111A2E    + border rgba(255,255,255,0.06)
surface-hover: #152038
primary:       #10B981
secondary:     #3B82F6
warn:          #F59E0B
error:         #EF4444
text:          #F1F5F9
text-muted:    #94A3B8
font-ui:       Inter
font-mono:     JetBrains Mono
type scale:    11 / 12 / 14 / 16 / 20 / 28 / 36
radius:        6 (button) / 12 (card) / 999 (pill)
spacing:       4 / 8 / 12 / 16 / 24 / 32
shadow:        QGraphicsDropShadowEffect blur=24 alpha=60
```

Light theme override các giá trị tương ứng. QSS file `dark.qss` + `light.qss`, hot-swap khi user đổi theme.

### 7.2. Shell layout

- Frameless window, custom title bar (logo + tên app + nút min/max/close).
- Sidebar 220px, item active có vạch dọc emerald + nền sáng hơn.
- Status bar dưới: 4 indicator chấm tròn (Camera / UART / Model / FPS) + đồng hồ.
- System tray: icon, menu Show/Pause/Exit, balloon notification khi UART mất kết nối.

### 7.3. Tab Live

- Video view 16:9, bbox + label chip (emerald conf≥0.8, amber 0.5–0.8, red <0.5).
- ROI editor: bấm icon ô vuông → kéo chuột vẽ vùng, lưu vào config.
- Detection stream phải: slide-in 200ms, fade sau 5s.
- 6 stat card dưới: Today / FPS / Latency / UART / Total / Accuracy.
- Pause = freeze frame (tracker vẫn nhớ). Snapshot = ghi `%APPDATA%/TrashSorter/snapshots/`.

### 7.4. Tab Lịch sử

- Filter: theo ngày, theo class, theo ack status.
- 2 chart pyqtgraph: bar phân bố theo class, area chart timeline theo giờ.
- Bảng virtualized 200 row/trang, click row mở dialog ảnh full + bbox.
- Export CSV và export folder ảnh JPEG.

### 7.5. Tab Mapping

- Drag handle ⠿ sắp lại priority.
- Mỗi class: input command (1 ký tự A–Z), bin index (1–9), Test button.
- Protocol preview live: gõ command → hiển thị byte-stream sẽ gửi.
- Lưu = update `AppConfig.mappings`, không cần restart.

### 7.6. Tab Capture

- Mode: Manual / Auto khi conf < threshold / Tắt.
- Grid thumbnail 6 cột, click → mini-labeler vẽ bbox + chọn class.
- Export YOLO format: tạo folder con `images/` + `labels/` + `data.yaml` đúng schema Ultralytics.

### 7.7. Tab Cài đặt

- Section card: Camera / Model / UART / Ứng dụng.
- Mỗi section có Test button → không phải save mới biết sai.
- Slider custom QSS (track gradient emerald, handle tròn).
- Save → atomic write config (write `.tmp` rồi `os.replace`).

### 7.8. Polish

- Toast notification góc trên phải, slide-in 200ms, auto-dismiss 4s.
- Skeleton loaders shimmer khi load history / model.
- Hover transition trên button/card (translateY -1px).
- Empty state mỗi tab có illustration SVG + hướng dẫn.
- Splash 1.5s khi khởi động, hiện logo + "Loading model…".
- Keyboard shortcut: `Ctrl+1..5` đổi tab, `Space` pause, `S` snapshot, `Ctrl+,` settings, `Ctrl+Q` quit.
- About dialog: version, model `names`, input size, link GitHub.

## 8. Testing strategy

### 8.1. Test pyramid

```
tests/
├── unit/
│   ├── test_config.py            # pydantic validate, default, save/load atomic
│   ├── test_tracker.py           # ByteTrack id stability, timeout 30 frame
│   ├── test_uart_protocol.py     # encode/decode SORT/ACK/NACK
│   ├── test_history.py           # CRUD, schema migration, export CSV
│   ├── test_mapping.py           # class→command, drag reorder
│   └── test_capture.py           # auto/manual mode, YOLO export schema
├── integration/
│   ├── test_inference.py         # load best.pt, infer ảnh fixture, ≥1 bbox
│   ├── test_camera_mock.py       # CameraWorker với MockCamera (folder ảnh)
│   ├── test_uart_loopback.py     # virtual COM, full lifecycle có timeout
│   └── test_pipeline_e2e.py      # ảnh fixture → infer → tracker → uart mock
└── ui/
    └── test_smoke.py             # pytest-qt: app khởi động, click 5 tab, không crash
```

### 8.2. Coverage gates

| Module | Lines | Branches |
|---|---|---|
| `core/` | ≥ 80% | ≥ 70% |
| `ui/` | ≥ 50% | ≥ 40% |
| `tests/` itself | n/a | n/a |

CI fail nếu coverage tụt dưới threshold (`pytest --cov-fail-under=80` cho `core`).

### 8.3. Manual test checklist (mỗi release)

- [ ] Camera unplug giữa runtime → status đỏ, auto-reconnect khi cắm lại.
- [ ] UART cable rút giữa runtime → status đỏ, queue command, flush khi reconnect.
- [ ] Đổi tên `best.pt` → modal yêu cầu chọn lại.
- [ ] Threshold = 0.0 và 1.0 → không crash, behavior đúng (mọi/none detection).
- [ ] Drag confidence slider liên tục 30s → UI không lag, no leak.
- [ ] Chạy 1000 detection liên tiếp → RSS tăng ≤ 50MB.
- [ ] Switch theme dark↔light 20 lần → no crash, mọi widget update.
- [ ] Minimize to tray, click tray icon → window hiện lại đúng vị trí cũ.
- [ ] Keyboard shortcut tất cả → đúng tác dụng.
- [ ] Build .exe → chạy trên máy Windows sạch (không có Python) → khởi động OK.

## 9. Tooling & dependencies

### 9.1. `pyproject.toml`

```toml
[project]
name = "trash-sorter"
version = "2.0.0"
description = "Trash classification desktop app with YOLO + UART"
requires-python = ">=3.10,<3.13"
dependencies = [
  "ultralytics>=8.3,<9.0",
  "opencv-python>=4.10,<5.0",
  "pyside6>=6.7,<7.0",
  "pyserial>=3.5,<4.0",
  "pydantic>=2.8,<3.0",
  "pyqtgraph>=0.13,<0.14",
  "qtawesome>=1.3,<2.0",
  "sqlalchemy>=2.0,<3.0",
  "loguru>=0.7,<1.0",
  "numpy>=1.26,<3.0",
  "pillow>=10.0,<12.0",
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-qt>=4.4",
  "pytest-cov>=5.0",
  "ruff>=0.6",
  "mypy>=1.11",
  "pre-commit>=3.8",
  "pyinstaller>=6.10",
]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
strict = true
files = ["app/core"]

[tool.pytest.ini_options]
testpaths = ["tests"]
qt_api = "pyside6"
```

### 9.2. Quy ước

- Dependency manager: **uv** (nhanh, lockfile reproducible).
- Format + lint: **ruff** (replace black + isort + flake8).
- Type check: **mypy --strict** chỉ cho `core/`.
- Pre-commit: ruff format + ruff check + mypy + pytest unit.
- Conventional Commits cho commit message.

## 10. Distribution

### 10.1. Dev

```
uv sync
uv run python -m app
```

### 10.2. Build

```
uv run python scripts/build_exe.py
```

Output: `dist/TrashSorterPro/` (one-folder PyInstaller). Bao gồm:
- `TrashSorterPro.exe` (entry).
- `_internal/` runtime + Python + libs.
- `models/best.pt` copy vào.
- `config.example.json`.

### 10.3. Installer (phase sau)

Inno Setup script `installer/setup.iss` → `TrashSorterPro-Setup-2.0.exe`. Tạo Start Menu shortcut, tuỳ chọn autostart, icon desktop.

## 11. Architecture decisions (ADR)

Sẽ tạo trong `docs/adr/`:
- **ADR-0001** Record architecture decisions.
- **ADR-0002** PySide6 over PyQt5 (LGPL friendlier, modern Qt6, official Qt Group).
- **ADR-0003** ByteTrack chosen for tracking (lightweight, không phụ thuộc deep model phụ).
- **ADR-0004** UART text protocol (`SORT:<cmd>:<conf>\n`) over binary (debug bằng PuTTY dễ).
- **ADR-0005** SQLite local-first (no server dependency, web phase 2 dùng API riêng).
- **ADR-0006** uv over poetry (build reproducible nhanh hơn).

## 12. Roadmap

### Phase 1 (spec này) — Desktop v2

Milestones:

1. **M1 Skeleton** (1 ngày): repo init, `uv sync`, app khởi động được Qt window trống, CI green.
2. **M2 Core pipeline** (2 ngày): camera → infer → tracker → uart mock, không UI, log ra console.
3. **M3 UI shell + Live tab** (1 ngày): sidebar, title bar, video view với bbox, status bar.
4. **M4 Settings + Mapping** (1 ngày): 2 tab cấu hình, atomic save, hot-reload model.
5. **M5 History + Capture** (1 ngày): SQLite, chart, export CSV, capture low-conf.
6. **M6 Polish + Test** (1 ngày): toast, skeleton, animation, full test suite, coverage gate.
7. **M7 Build + Manual QA** (0.5 ngày): PyInstaller, manual checklist, release v2.0.0.

Tổng: ~7.5 ngày làm việc.

### Phase 2 (spec riêng sau) — Web online

- Backend FastAPI (Python) reuse `app.core.inference`, `app.core.config`.
- Frontend Next.js 16 (Vercel-ready), dashboard live + history.
- Edge agent: desktop app push detection event (HMAC-signed) lên backend.
- Auth Clerk (Vercel Marketplace).
- DB Postgres (Neon). Realtime qua SSE.

### Phase 3 (tương lai) — Edge optimizations

- TensorRT export model `.pt` → `.engine` cho NVIDIA Jetson.
- Multi-camera + multi-UART.
- Voice feedback ("đã phân loại nhựa") qua TTS.

## 13. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Tracker mis-id nhiều object cùng class trong frame | Sai lệnh UART | Tune ByteTrack params; manual test với fixture nhiều object |
| Model `best.pt` không match input shape mới | Crash | Validate `model.task` + `imgsz` lúc load, modal cảnh báo |
| Windows COM port name khác sau reboot | UART fail | Dropdown auto-scan, persistent config + hint nếu mismatch |
| YOLO inference quá chậm trên CPU yếu | Backlog frame | Skip-frame strategy + adjustable target FPS |
| User vô tình chỉnh threshold = 1.0 | Không có detection nào | UI hint "Quá cao - sẽ không phát hiện gì" khi > 0.9 |
| Frameless window khó kéo trên multi-monitor | UX bug | Test multi-monitor manually, fallback bật native frame qua flag |
| PyInstaller miss DLL của ultralytics/torch | Build run được dev, fail user | Test build trên máy Windows clean trước mỗi release |

## 14. Open questions

Tất cả câu hỏi đã giải quyết qua brainstorm. Nếu phát sinh trong implementation, cập nhật ở phần này và bump version spec.

## 15. References

- Dataset gốc: https://universe.roboflow.com/projectverba/yolo-waste-detection
- Ultralytics YOLO docs: https://docs.ultralytics.com
- PySide6 docs: https://doc.qt.io/qtforpython-6
- ByteTrack paper: https://arxiv.org/abs/2110.06864
- pyqtgraph: https://www.pyqtgraph.org
- qtawesome (icon set): https://github.com/spyder-ide/qtawesome
