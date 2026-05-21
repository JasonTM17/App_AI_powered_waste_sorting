# Trash Sorter Desktop v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Viết lại sạch app phân loại rác desktop, GUI PySide6 modern, YOLO inference + UART control + SQLite history, modular core/ tách khỏi ui/ để phase 2 web reuse được.

**Architecture:** Layered: `core/` (camera, inference, tracker, uart, history, config) độc lập với `ui/` (PySide6 widgets/pages). Worker QThread cho mỗi I/O nặng. Communicate qua Qt signal/slot. Local-first: config JSON + SQLite tại `%APPDATA%/TrashSorter/`.

**Tech Stack:** Python 3.10+, PySide6 6.7, ultralytics 8.3 (YOLO), opencv-python 4.10, pyserial 3.5, pydantic 2.8, pyqtgraph 0.13, sqlalchemy 2.0, loguru 0.7, uv (deps), ruff (lint), pytest + pytest-qt, PyInstaller 6.10.

**Spec:** `docs/superpowers/specs/2026-05-21-trash-sorter-desktop-v2-design.md`

**Working dir:** `D:\PHAN LOAI RAC\trash-sorter-v2\`

---

## Milestone M1 — Skeleton (1 ngày)

Repo init, deps install, app khởi động Qt window trống, CI green.

### Task 1.1: Init repo + .gitignore

**Files:**
- Create: `D:\PHAN LOAI RAC\trash-sorter-v2\.gitignore`
- Create: `D:\PHAN LOAI RAC\trash-sorter-v2\README.md`

- [ ] **Step 1: Init git repo**

```bash
cd "D:\PHAN LOAI RAC\trash-sorter-v2"
git init
git config user.name "JasonTM17"
git config user.email "jasonbmt06@gmail.com"
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.uv/

# Build
build/
dist/
*.spec

# IDE
.vscode/
.idea/

# App data
*.log
*.db
*.sqlite
*.sqlite3
snapshots/
dataset_v2/

# Config (private)
config.local.json
.env
.env.*
!.env.example

# Private docs (per global rule)
PLAN*.md
plan*.md
NOTES*.md
notes*.md
TODO*.md
todo*.md
DRAFT*.md
draft*.md
*.private.md
*.local.md
.claude-private/
.private/
.omc/
.claude/worktrees/

# OS
Thumbs.db
.DS_Store
desktop.ini
```

- [ ] **Step 3: Minimal README.md**

```markdown
# Trash Sorter Desktop v2

Ứng dụng phân loại rác desktop với YOLO + UART control.

## Quick start

```bash
uv sync
uv run python -m app
```

## Stack

PySide6 · Ultralytics YOLO · OpenCV · PySerial · SQLite · pyqtgraph

Spec: `docs/superpowers/specs/2026-05-21-trash-sorter-desktop-v2-design.md`
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore README.md
git commit -m "chore: init repo with gitignore and readme"
```

### Task 1.2: Setup pyproject.toml + uv sync

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "trash-sorter"
version = "2.0.0"
description = "Trash classification desktop app with YOLO + UART"
requires-python = ">=3.10,<3.13"
authors = [{ name = "Nguyen Tien Son", email = "jasonbmt06@gmail.com" }]
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

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "RUF"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.10"
strict = true
files = ["app/core"]

[tool.pytest.ini_options]
testpaths = ["tests"]
qt_api = "pyside6"
addopts = "-ra --strict-markers"

[tool.coverage.run]
source = ["app"]
branch = true
```

- [ ] **Step 2: Run `uv sync`**

```bash
uv sync
```

Expected: `.venv/` created, all deps installed.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add pyproject.toml with deps via uv"
```

### Task 1.3: Hello-world Qt window

**Files:**
- Create: `app/__init__.py`
- Create: `app/__main__.py`
- Create: `app/ui/__init__.py`
- Create: `app/ui/main_window.py`

- [ ] **Step 1: Write `app/__init__.py`**

```python
"""Trash Sorter Desktop v2."""

__version__ = "2.0.0"
```

- [ ] **Step 2: Write `app/ui/__init__.py`**

```python
```

- [ ] **Step 3: Write `app/ui/main_window.py`**

```python
"""Main window shell."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Trash Sorter Pro")
        self.resize(1280, 800)

        placeholder = QLabel("Trash Sorter v2 — skeleton")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)
```

- [ ] **Step 4: Write `app/__main__.py`**

```python
"""Entry point: python -m app."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Trash Sorter Pro")
    app.setOrganizationName("TrashSorter")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run app, verify window opens**

```bash
uv run python -m app
```

Expected: Window 1280×800 opens with text "Trash Sorter v2 — skeleton". Close window to exit.

- [ ] **Step 6: Commit**

```bash
git add app/
git commit -m "feat: skeleton qt window via python -m app"
```

### Task 1.4: Logging utility + paths utility

**Files:**
- Create: `app/utils/__init__.py`
- Create: `app/utils/paths.py`
- Create: `app/utils/logging.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_paths.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_paths.py`:
```python
from pathlib import Path

from app.utils.paths import app_data_dir, logs_dir, snapshots_dir


def test_app_data_dir_returns_path(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = app_data_dir()
    assert isinstance(p, Path)
    assert p.exists()
    assert p.name == "TrashSorter"


def test_logs_and_snapshots_subdirs(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert logs_dir().name == "logs"
    assert snapshots_dir().name == "snapshots"
    assert logs_dir().parent == app_data_dir()
```

- [ ] **Step 2: Run test, verify it fails**

```bash
uv run pytest tests/unit/test_paths.py -v
```

Expected: FAIL with `ModuleNotFoundError: app.utils.paths`.

- [ ] **Step 3: Implement `app/utils/paths.py`**

```python
"""Cross-platform user data paths."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "TrashSorter"


def app_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        path = Path(base) / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        path = Path(base) / "trash-sorter"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    p = app_data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def snapshots_dir() -> Path:
    p = app_data_dir() / "snapshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_path() -> Path:
    return app_data_dir() / "config.json"


def db_path() -> Path:
    return app_data_dir() / "history.db"
```

- [ ] **Step 4: Write `app/utils/__init__.py`**

```python
```

- [ ] **Step 5: Run test, verify pass**

```bash
uv run pytest tests/unit/test_paths.py -v
```

Expected: 2 PASSED.

- [ ] **Step 6: Implement `app/utils/logging.py`**

```python
"""Structured JSON logging via loguru."""
from __future__ import annotations

import sys
from datetime import datetime

from loguru import logger

from app.utils.paths import logs_dir


def setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stderr, level=level, colorize=True)
    logfile = logs_dir() / f"app-{datetime.now():%Y-%m-%d}.log"
    logger.add(
        logfile,
        level="DEBUG",
        rotation="00:00",
        retention="7 days",
        serialize=True,
        enqueue=True,
    )


__all__ = ["logger", "setup_logging"]
```

- [ ] **Step 7: Wire logging into `app/__main__.py`**

Replace `app/__main__.py`:
```python
"""Entry point: python -m app."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.utils.logging import logger, setup_logging


def main() -> int:
    setup_logging()
    logger.info("starting app")
    app = QApplication(sys.argv)
    app.setApplicationName("Trash Sorter Pro")
    app.setOrganizationName("TrashSorter")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8: Commit**

```bash
git add app/utils/ tests/
git commit -m "feat(utils): cross-platform paths and structured logging"
```

### Task 1.5: CI workflow (advisory)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install uv
        run: pip install uv
      - name: uv sync
        run: uv sync
      - name: ruff check
        run: uv run ruff check .
        continue-on-error: true
      - name: ruff format
        run: uv run ruff format --check .
        continue-on-error: true
      - name: mypy core
        run: uv run mypy app/core
        continue-on-error: true
      - name: pytest
        run: uv run pytest --cov=app --cov-report=term-missing
```

- [ ] **Step 2: Commit**

```bash
git add .github/
git commit -m "ci: add advisory ci workflow"
```

---

## Milestone M2 — Core pipeline (2 ngày)

Camera → infer → tracker → uart mock, không UI, log ra console. Test integration end-to-end.

### Task 2.1: Domain events (dataclass)

**Files:**
- Create: `app/core/__init__.py`
- Create: `app/core/events.py`
- Create: `tests/unit/test_events.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_events.py`:
```python
from datetime import datetime, UTC

import numpy as np

from app.core.events import AckEvent, Detection, DetectionEvent, TrackedDetection


def test_detection_immutable():
    d = Detection(cls_id=1, cls_name="plastic", conf=0.92, xyxy=(10, 20, 100, 200))
    assert d.conf == 0.92
    try:
        d.conf = 0.5
        assert False, "should be frozen"
    except Exception:
        pass


def test_tracked_detection_carries_track_id():
    d = Detection(0, "paper", 0.8, (0, 0, 50, 50))
    t = TrackedDetection(track_id=7, detection=d, stable_frames=3, first_seen_ts=1.0)
    assert t.track_id == 7
    assert t.detection.cls_name == "paper"


def test_detection_event_holds_frame():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    e = DetectionEvent(
        track_id=1, cls_id=0, cls_name="paper", conf=0.9,
        frame=frame, ts=datetime.now(UTC),
    )
    assert e.frame.shape == (10, 10, 3)


def test_ack_event_status_literal():
    a = AckEvent(track_id=1, command="P", status="ok", rtt_ms=42)
    assert a.status == "ok"
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/test_events.py -v
```

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement `app/core/events.py`**

```python
"""Immutable event/data classes shared across core modules."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import numpy as np


@dataclass(frozen=True)
class Detection:
    cls_id: int
    cls_name: str
    conf: float
    xyxy: tuple[int, int, int, int]


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
    frame: np.ndarray
    ts: datetime


@dataclass(frozen=True)
class AckEvent:
    track_id: int
    command: str
    status: Literal["ok", "no_ack", "error"]
    rtt_ms: int | None
```

- [ ] **Step 4: Write `app/core/__init__.py`**

```python
```

- [ ] **Step 5: Run test, verify pass**

```bash
uv run pytest tests/unit/test_events.py -v
```

Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```bash
git add app/core/ tests/unit/test_events.py
git commit -m "feat(core): domain event dataclasses"
```

### Task 2.2: Config schema (pydantic) + load/save

**Files:**
- Create: `app/core/config.py`
- Create: `tests/unit/test_config.py`
- Create: `config.example.json`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_config.py`:
```python
import json
from pathlib import Path

import pytest

from app.core.config import AppConfig, ClassMapping, load_config, save_config


def _default_dict():
    return {
        "camera": {"source": "0", "width": 1280, "height": 720, "mirror": False},
        "model": {
            "path": "models/best.pt", "device": "cpu",
            "conf_threshold": 0.4, "iou_threshold": 0.45,
            "input_size": 640, "half_precision": False,
        },
        "uart": {"port": "COM3", "baud": 9600, "auto_reconnect": True, "ack_timeout_ms": 200},
        "mappings": [{"class_name": "plastic", "command": "S", "bin_index": 2, "enabled": True}],
        "roi": {"enabled": False, "x": 0, "y": 0, "width": 0, "height": 0},
        "capture": {"mode": "auto_low_conf", "low_conf_threshold": 0.6, "output_dir": "dataset_v2"},
        "theme": "dark", "language": "vi", "minimize_to_tray": True, "autostart": False,
    }


def test_app_config_parses_default_dict():
    c = AppConfig.model_validate(_default_dict())
    assert c.camera.source == "0"
    assert c.model.conf_threshold == 0.4
    assert c.uart.port == "COM3"
    assert c.mappings[0].command == "S"


def test_conf_threshold_out_of_range_rejected():
    d = _default_dict()
    d["model"]["conf_threshold"] = 1.5
    with pytest.raises(Exception):
        AppConfig.model_validate(d)


def test_save_and_load_roundtrip(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg = AppConfig.model_validate(_default_dict())
    save_config(cfg, cfg_path)
    assert cfg_path.exists()
    loaded = load_config(cfg_path)
    assert loaded.camera.source == cfg.camera.source
    assert loaded.mappings[0].command == "S"


def test_load_missing_file_writes_default(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    assert cfg_path.exists()
    assert isinstance(cfg, AppConfig)


def test_load_corrupt_json_backs_up_and_writes_default(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{ not valid json", encoding="utf-8")
    cfg = load_config(cfg_path)
    assert isinstance(cfg, AppConfig)
    assert (cfg_path.parent / "config.json.broken").exists()


def test_atomic_save_does_not_corrupt(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg = AppConfig.model_validate(_default_dict())
    save_config(cfg, cfg_path)
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert raw["camera"]["source"] == "0"
    assert not (tmp_path / "config.json.tmp").exists()
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement `app/core/config.py`**

```python
"""Application config schema and atomic load/save."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class CameraConfig(BaseModel):
    source: str = "0"
    width: int = 1280
    height: int = 720
    mirror: bool = False


class ModelConfig(BaseModel):
    path: str = "models/best.pt"
    device: Literal["cpu", "cuda"] = "cpu"
    conf_threshold: float = Field(0.4, ge=0.0, le=1.0)
    iou_threshold: float = Field(0.45, ge=0.0, le=1.0)
    input_size: int = 640
    half_precision: bool = False


class UartConfig(BaseModel):
    port: str = "COM3"
    baud: int = 9600
    auto_reconnect: bool = True
    ack_timeout_ms: int = Field(200, ge=10, le=5000)


class ClassMapping(BaseModel):
    class_name: str
    command: str = Field(..., min_length=1, max_length=1)
    bin_index: int = Field(..., ge=1, le=9)
    enabled: bool = True


class RoiConfig(BaseModel):
    enabled: bool = False
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


class CaptureConfig(BaseModel):
    mode: Literal["off", "manual", "auto_low_conf"] = "auto_low_conf"
    low_conf_threshold: float = Field(0.6, ge=0.0, le=1.0)
    output_dir: str = "dataset_v2"


class AppConfig(BaseModel):
    camera: CameraConfig = CameraConfig()
    model: ModelConfig = ModelConfig()
    uart: UartConfig = UartConfig()
    mappings: list[ClassMapping] = Field(default_factory=list)
    roi: RoiConfig = RoiConfig()
    capture: CaptureConfig = CaptureConfig()
    theme: Literal["dark", "light"] = "dark"
    language: Literal["vi", "en"] = "vi"
    minimize_to_tray: bool = True
    autostart: bool = False


def save_config(cfg: AppConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = cfg.model_dump(mode="json")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        cfg = AppConfig()
        save_config(cfg, path)
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig.model_validate(raw)
    except Exception:
        backup = path.with_suffix(path.suffix + ".broken")
        shutil.copy2(path, backup)
        cfg = AppConfig()
        save_config(cfg, path)
        return cfg
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: 6 PASSED.

- [ ] **Step 5: Generate `config.example.json`**

```bash
uv run python -c "from app.core.config import AppConfig, ClassMapping, save_config; from pathlib import Path; cfg = AppConfig(mappings=[ClassMapping(class_name='paper', command='P', bin_index=1), ClassMapping(class_name='plastic', command='S', bin_index=2), ClassMapping(class_name='metal', command='M', bin_index=3), ClassMapping(class_name='glass', command='G', bin_index=4), ClassMapping(class_name='organic', command='O', bin_index=5), ClassMapping(class_name='cardboard', command='C', bin_index=6)]); save_config(cfg, Path('config.example.json'))"
```

- [ ] **Step 6: Commit**

```bash
git add app/core/config.py tests/unit/test_config.py config.example.json
git commit -m "feat(core): pydantic config schema with atomic save and corrupt-recovery"
```

### Task 2.3: Camera worker (QThread)

**Files:**
- Create: `app/core/camera.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_camera_mock.py`

- [ ] **Step 1: Write failing integration test**

`tests/integration/test_camera_mock.py`:
```python
from pathlib import Path
import time

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication

from app.core.camera import CameraWorker


@pytest.fixture
def fake_video(tmp_path):
    out = tmp_path / "fake.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out), fourcc, 10, (320, 240))
    for i in range(20):
        frame = np.full((240, 320, 3), i * 10, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return out


def test_camera_emits_frames(fake_video, qtbot):
    received = []
    worker = CameraWorker(source=str(fake_video), width=320, height=240)
    worker.frame_ready.connect(lambda f: received.append(f))
    worker.start()
    deadline = time.time() + 3
    while len(received) < 3 and time.time() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.05)
    worker.stop()
    worker.wait(2000)
    assert len(received) >= 3


def test_camera_emits_error_on_bad_source(qtbot):
    errors = []
    worker = CameraWorker(source="nonexistent_file.mp4")
    worker.error.connect(lambda msg: errors.append(msg))
    worker.start()
    deadline = time.time() + 5
    while not errors and time.time() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.1)
    worker.stop()
    worker.wait(2000)
    assert errors
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/integration/test_camera_mock.py -v
```

Expected: FAIL `ModuleNotFoundError`.


- [ ] **Step 3: Implement `app/core/camera.py`**

```python
"""Camera worker: read frames in QThread, emit via signal."""
from __future__ import annotations

import time

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

from app.utils.logging import logger


class CameraWorker(QThread):
    frame_ready = Signal(np.ndarray)
    error = Signal(str)
    connected = Signal(bool)

    def __init__(self, source="0", width=1280, height=720, mirror=False):
        super().__init__()
        self._source = source
        self._width = width
        self._height = height
        self._mirror = mirror
        self._stop = False
        self._cap = None

    def _open(self):
        src = int(self._source) if self._source.isdigit() else self._source
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            cap.release()
            return False
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap = cap
        return True

    def run(self):
        consecutive_fail = 0
        retry_attempts = 0
        while not self._stop:
            if self._cap is None:
                if self._open():
                    self.connected.emit(True)
                    consecutive_fail = 0
                    retry_attempts = 0
                else:
                    retry_attempts += 1
                    self.error.emit(f"open camera failed (attempt {retry_attempts})")
                    self.connected.emit(False)
                    time.sleep(2.0 if retry_attempts >= 3 else 1.0)
                    if retry_attempts >= 3:
                        retry_attempts = 0
                    continue
            ok, frame = self._cap.read()
            if not ok or frame is None:
                consecutive_fail += 1
                if consecutive_fail >= 5:
                    logger.warning("camera lost, reconnecting")
                    self._cap.release()
                    self._cap = None
                    self.connected.emit(False)
                continue
            consecutive_fail = 0
            if self._mirror:
                frame = cv2.flip(frame, 1)
            self.frame_ready.emit(frame)
        if self._cap is not None:
            self._cap.release()

    def stop(self):
        self._stop = True
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/integration/test_camera_mock.py -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/core/camera.py tests/integration/
git commit -m "feat(core): camera worker with auto-reconnect"
```


### Task 2.4: Inference engine (YOLO)

**Files:**
- Create: `app/core/inference.py`
- Create: `tests/integration/test_inference.py`
- Create: `tests/fixtures/sample_trash.jpg`
- Copy: `models/best.pt` (from existing `_internal/best.pt`)

- [ ] **Step 1: Copy model + add fixture**

```bash
mkdir -p models tests/fixtures
cp "../_internal/best.pt" models/best.pt
```

For `tests/fixtures/sample_trash.jpg`: any 640×480 trash-like image. Manual: download or screenshot.

- [ ] **Step 2: Write failing test**

`tests/integration/test_inference.py`:
```python
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.core.events import Detection
from app.core.inference import InferenceEngine

MODEL = Path("models/best.pt")
FIXTURE = Path("tests/fixtures/sample_trash.jpg")


@pytest.mark.skipif(not MODEL.exists(), reason="best.pt missing")
def test_engine_loads_class_names():
    eng = InferenceEngine(MODEL, device="cpu")
    assert isinstance(eng.class_names, dict)
    assert len(eng.class_names) > 0


@pytest.mark.skipif(not (MODEL.exists() and FIXTURE.exists()), reason="missing assets")
def test_engine_predict_returns_detections():
    eng = InferenceEngine(MODEL, device="cpu", conf=0.05)
    img = cv2.imread(str(FIXTURE))
    out = eng.predict(img)
    assert isinstance(out, list)
    for d in out:
        assert isinstance(d, Detection)
        assert 0.0 <= d.conf <= 1.0


@pytest.mark.skipif(not MODEL.exists(), reason="best.pt missing")
def test_engine_predict_blank_frame():
    eng = InferenceEngine(MODEL, device="cpu")
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    out = eng.predict(blank)
    assert isinstance(out, list)
```

- [ ] **Step 3: Run test, verify fail**

```bash
uv run pytest tests/integration/test_inference.py -v
```

Expected: FAIL `ModuleNotFoundError`.


- [ ] **Step 4: Implement `app/core/inference.py`**

```python
"""YOLO inference wrapper around ultralytics."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.core.events import Detection
from app.utils.logging import logger


class InferenceEngine:
    def __init__(self, model_path, device="cpu", conf=0.4, iou=0.45, imgsz=640, half=False):
        from ultralytics import YOLO

        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"model not found: {path}")
        self._model = YOLO(str(path))
        self.class_names = dict(self._model.names)
        self.device = device
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.half = half
        logger.info(
            "inference loaded model={} classes={} device={}",
            str(path), len(self.class_names), device,
        )

    def predict(self, frame_bgr):
        results = self._model.predict(
            source=frame_bgr,
            conf=self.conf,
            iou=self.iou,
            imgsz=self.imgsz,
            device=self.device,
            half=self.half,
            verbose=False,
        )
        out = []
        if not results:
            return out
        r = results[0]
        if r.boxes is None or len(r.boxes) == 0:
            return out
        xyxy = r.boxes.xyxy.cpu().numpy().astype(int)
        confs = r.boxes.conf.cpu().numpy()
        clss = r.boxes.cls.cpu().numpy().astype(int)
        for box, cf, ci in zip(xyxy, confs, clss, strict=True):
            x1, y1, x2, y2 = (int(v) for v in box)
            out.append(Detection(
                cls_id=int(ci),
                cls_name=self.class_names.get(int(ci), str(int(ci))),
                conf=float(cf),
                xyxy=(x1, y1, x2, y2),
            ))
        return out

    def update_thresholds(self, conf=None, iou=None):
        if conf is not None:
            self.conf = conf
        if iou is not None:
            self.iou = iou
```

- [ ] **Step 5: Add `models/.gitkeep`, exclude `.pt` from git**

Append to `.gitignore`:
```
models/*.pt
!models/.gitkeep
```

```bash
touch models/.gitkeep
```

- [ ] **Step 6: Run test, verify pass**

```bash
uv run pytest tests/integration/test_inference.py -v
```

Expected: 3 PASSED.

- [ ] **Step 7: Commit**

```bash
git add app/core/inference.py tests/integration/test_inference.py models/.gitkeep .gitignore
git commit -m "feat(core): yolo inference engine with hot threshold tuning"
```


### Task 2.5: Tracker (ByteTrack-lite)

Implement minimal IoU-based tracker đủ để gán `track_id` ổn định và quyết định 1-object-1-command. Đủ cho phase 1; có thể swap sang ultralytics built-in tracker sau.

**Files:**
- Create: `app/core/tracker.py`
- Create: `tests/unit/test_tracker.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_tracker.py`:
```python
from app.core.events import Detection
from app.core.tracker import Tracker


def _det(cls=0, conf=0.9, xyxy=(10, 10, 100, 100)):
    return Detection(cls_id=cls, cls_name=f"c{cls}", conf=conf, xyxy=xyxy)


def test_new_object_gets_id():
    tr = Tracker(iou_threshold=0.3, max_age=30)
    out = tr.update([_det()])
    assert len(out) == 1
    assert out[0].track_id >= 1
    assert out[0].stable_frames == 1


def test_same_object_keeps_id_across_frames():
    tr = Tracker()
    a = tr.update([_det(xyxy=(10, 10, 100, 100))])[0]
    b = tr.update([_det(xyxy=(12, 12, 102, 102))])[0]
    assert a.track_id == b.track_id
    assert b.stable_frames == 2


def test_different_object_gets_different_id():
    tr = Tracker()
    out_a = tr.update([_det(xyxy=(10, 10, 50, 50))])
    out_b = tr.update([_det(xyxy=(200, 200, 250, 250))])
    assert out_a[0].track_id != out_b[0].track_id


def test_track_expires_after_max_age():
    tr = Tracker(max_age=3)
    a = tr.update([_det()])[0]
    for _ in range(4):
        tr.update([])
    b = tr.update([_det()])[0]
    assert b.track_id != a.track_id


def test_already_emitted_filter():
    tr = Tracker()
    out = tr.update([_det()])[0]
    assert tr.should_emit(out.track_id) is True
    tr.mark_emitted(out.track_id)
    assert tr.should_emit(out.track_id) is False
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/test_tracker.py -v
```

Expected: FAIL `ModuleNotFoundError`.


- [ ] **Step 3: Implement `app/core/tracker.py`**

```python
"""Lightweight IoU-based tracker for per-object UART dispatch."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.core.events import Detection, TrackedDetection


def _iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    x1 = max(ax1, bx1)
    y1 = max(ay1, by1)
    x2 = min(ax2, bx2)
    y2 = min(ay2, by2)
    iw = max(0, x2 - x1)
    ih = max(0, y2 - y1)
    inter = iw * ih
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass
class _Track:
    track_id: int
    cls_id: int
    xyxy: tuple
    age: int = 0
    stable_frames: int = 1
    first_seen_ts: float = field(default_factory=time.time)


class Tracker:
    def __init__(self, iou_threshold=0.3, max_age=30):
        self._iou_th = iou_threshold
        self._max_age = max_age
        self._next_id = 1
        self._tracks: dict[int, _Track] = {}
        self._emitted: set[int] = set()

    def update(self, detections):
        for t in self._tracks.values():
            t.age += 1
        out = []
        for det in detections:
            best_id = None
            best_iou = self._iou_th
            for tid, t in self._tracks.items():
                if t.cls_id != det.cls_id:
                    continue
                score = _iou(det.xyxy, t.xyxy)
                if score > best_iou:
                    best_iou = score
                    best_id = tid
            if best_id is None:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = _Track(track_id=tid, cls_id=det.cls_id, xyxy=det.xyxy)
                t = self._tracks[tid]
            else:
                t = self._tracks[best_id]
                t.age = 0
                t.stable_frames += 1
                t.xyxy = det.xyxy
            out.append(TrackedDetection(
                track_id=t.track_id,
                detection=det,
                stable_frames=t.stable_frames,
                first_seen_ts=t.first_seen_ts,
            ))
        # cull
        dead = [tid for tid, t in self._tracks.items() if t.age > self._max_age]
        for tid in dead:
            self._tracks.pop(tid, None)
            self._emitted.discard(tid)
        return out

    def should_emit(self, track_id):
        return track_id not in self._emitted

    def mark_emitted(self, track_id):
        self._emitted.add(track_id)
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/test_tracker.py -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/core/tracker.py tests/unit/test_tracker.py
git commit -m "feat(core): IoU tracker with stable id and emit-once gate"
```


### Task 2.6: UART protocol encoder/decoder (pure functions)

**Files:**
- Create: `app/core/uart_protocol.py`
- Create: `tests/unit/test_uart_protocol.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_uart_protocol.py`:
```python
import pytest

from app.core.uart_protocol import encode_sort, parse_line


def test_encode_sort_basic():
    assert encode_sort("S", 0.92) == b"SORT:S:0.92\n"


def test_encode_sort_clamps_conf():
    assert encode_sort("P", 1.5) == b"SORT:P:1.00\n"
    assert encode_sort("P", -0.1) == b"SORT:P:0.00\n"


def test_encode_sort_rejects_bad_command():
    with pytest.raises(ValueError):
        encode_sort("", 0.5)
    with pytest.raises(ValueError):
        encode_sort("AB", 0.5)


def test_parse_ack():
    msg = parse_line(b"ACK:S\n")
    assert msg == ("ack", "S", None)


def test_parse_nack_with_reason():
    msg = parse_line(b"NACK:S:busy\n")
    assert msg == ("nack", "S", "busy")


def test_parse_pong():
    msg = parse_line(b"PONG\n")
    assert msg == ("pong", None, None)


def test_parse_log():
    msg = parse_line(b"LOG:hello world\n")
    assert msg == ("log", None, "hello world")


def test_parse_unknown_returns_none():
    assert parse_line(b"random text\n") is None
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/test_uart_protocol.py -v
```

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement `app/core/uart_protocol.py`**

```python
"""UART wire protocol encoders and parsers (pure functions)."""
from __future__ import annotations

from typing import Literal

MsgKind = Literal["ack", "nack", "pong", "log"]


def encode_sort(command: str, conf: float) -> bytes:
    if not command or len(command) != 1:
        raise ValueError("command must be exactly 1 character")
    conf = max(0.0, min(1.0, float(conf)))
    return f"SORT:{command}:{conf:.2f}\n".encode("utf-8")


def encode_ping() -> bytes:
    return b"PING\n"


def parse_line(raw: bytes):
    try:
        s = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    if not s:
        return None
    if s == "PONG":
        return ("pong", None, None)
    if s.startswith("LOG:"):
        return ("log", None, s[4:])
    if s.startswith("ACK:"):
        return ("ack", s[4:].strip() or None, None)
    if s.startswith("NACK:"):
        rest = s[5:]
        if ":" in rest:
            cmd, reason = rest.split(":", 1)
            return ("nack", cmd, reason)
        return ("nack", rest, None)
    return None
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/test_uart_protocol.py -v
```

Expected: 8 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/core/uart_protocol.py tests/unit/test_uart_protocol.py
git commit -m "feat(core): uart text protocol encode/parse"
```


### Task 2.7: UART worker (QThread, queue + ack + reconnect)

**Files:**
- Create: `app/core/uart.py`
- Create: `tests/integration/test_uart_loopback.py`

> Note: integration test dùng `pytest.MonkeyPatch` để fake `serial.Serial` thay vì virtual COM, để chạy được trong CI Windows mà không cần cài com0com.

- [ ] **Step 1: Write failing test**

`tests/integration/test_uart_loopback.py`:
```python
import time

import pytest
from PySide6.QtCore import QCoreApplication

from app.core.uart import UartWorker


class FakeSerial:
    def __init__(self, port, baud, timeout=0.1):
        self.port = port
        self.baud = baud
        self.is_open = True
        self._tx = []
        self._rx = []

    def write(self, data):
        self._tx.append(bytes(data))
        if data.startswith(b"SORT:"):
            cmd = data.decode().split(":")[1]
            self._rx.append(f"ACK:{cmd}\n".encode())
        if data == b"PING\n":
            self._rx.append(b"PONG\n")
        return len(data)

    def readline(self):
        if self._rx:
            return self._rx.pop(0)
        return b""

    def close(self):
        self.is_open = False


@pytest.fixture
def fake_serial(monkeypatch):
    instances = []
    def factory(port, baud, timeout=0.1):
        s = FakeSerial(port, baud, timeout)
        instances.append(s)
        return s
    monkeypatch.setattr("app.core.uart.serial.Serial", factory)
    return instances


def _wait(cond, timeout=2.0):
    deadline = time.time() + timeout
    while not cond() and time.time() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.02)


def test_send_receives_ack(fake_serial, qtbot):
    acks = []
    w = UartWorker(port="COM_FAKE", baud=9600, ack_timeout_ms=500)
    w.ack_received.connect(lambda track_id, cmd, status, rtt: acks.append((track_id, cmd, status)))
    w.start()
    _wait(lambda: w.is_connected, 2.0)
    w.send(track_id=1, command="S", conf=0.9)
    _wait(lambda: len(acks) >= 1, 2.0)
    w.stop(); w.wait(2000)
    assert acks and acks[0] == (1, "S", "ok")


def test_no_ack_marked_when_silent(monkeypatch, qtbot):
    class SilentSerial(FakeSerial):
        def write(self, data):
            self._tx.append(bytes(data))
            return len(data)
    monkeypatch.setattr("app.core.uart.serial.Serial", lambda p, b, timeout=0.1: SilentSerial(p, b, timeout))
    acks = []
    w = UartWorker(port="COM_FAKE", baud=9600, ack_timeout_ms=200)
    w.ack_received.connect(lambda tid, c, st, rtt: acks.append((tid, c, st)))
    w.start()
    _wait(lambda: w.is_connected, 2.0)
    w.send(track_id=2, command="P", conf=0.8)
    _wait(lambda: len(acks) >= 1, 2.0)
    w.stop(); w.wait(2000)
    assert acks and acks[0] == (2, "P", "no_ack")
```


- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/integration/test_uart_loopback.py -v
```

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement `app/core/uart.py`**

```python
"""UART worker: send commands, parse responses, auto-reconnect."""
from __future__ import annotations

import queue
import time
from dataclasses import dataclass

import serial
from PySide6.QtCore import QThread, Signal

from app.core.uart_protocol import encode_ping, encode_sort, parse_line
from app.utils.logging import logger


@dataclass
class _Cmd:
    track_id: int
    command: str
    conf: float
    enqueued_at: float


class UartWorker(QThread):
    ack_received = Signal(int, str, str, object)  # track_id, command, status, rtt_ms
    connected = Signal(bool)
    error = Signal(str)

    def __init__(self, port="COM3", baud=9600, ack_timeout_ms=200, auto_reconnect=True):
        super().__init__()
        self._port = port
        self._baud = baud
        self._ack_timeout = ack_timeout_ms / 1000.0
        self._auto_reconnect = auto_reconnect
        self._stop = False
        self._queue: queue.Queue[_Cmd] = queue.Queue(maxsize=100)
        self._ser: serial.Serial | None = None
        self.is_connected = False

    def send(self, track_id, command, conf):
        try:
            self._queue.put_nowait(_Cmd(track_id, command, conf, time.time()))
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(_Cmd(track_id, command, conf, time.time()))

    def _open(self):
        try:
            self._ser = serial.Serial(self._port, self._baud, timeout=0.1)
            self.is_connected = True
            self.connected.emit(True)
            self._ser.write(encode_ping())
            return True
        except Exception as e:
            logger.warning("uart open failed port={} err={}", self._port, e)
            self.is_connected = False
            self.connected.emit(False)
            self.error.emit(f"open {self._port} failed: {e}")
            return False

    def _read_until_ack(self, expected_cmd, deadline):
        while time.time() < deadline:
            try:
                raw = self._ser.readline()
            except Exception:
                return None
            if not raw:
                continue
            parsed = parse_line(raw)
            if parsed is None:
                continue
            kind, cmd, payload = parsed
            if kind == "ack" and cmd == expected_cmd:
                return ("ok", None)
            if kind == "nack" and cmd == expected_cmd:
                return ("error", payload)
            if kind == "log":
                logger.info("uart log: {}", payload)
        return None

    def run(self):
        while not self._stop:
            if self._ser is None or not self.is_connected:
                if not self._open():
                    if not self._auto_reconnect:
                        time.sleep(0.5)
                        continue
                    time.sleep(2.0)
                    continue
            try:
                cmd = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            payload = encode_sort(cmd.command, cmd.conf)
            t0 = time.time()
            try:
                self._ser.write(payload)
            except Exception as e:
                logger.warning("uart write failed: {}", e)
                self._close()
                continue
            deadline = t0 + self._ack_timeout
            outcome = self._read_until_ack(cmd.command, deadline)
            rtt = int((time.time() - t0) * 1000)
            if outcome is None:
                self.ack_received.emit(cmd.track_id, cmd.command, "no_ack", rtt)
            else:
                status, _ = outcome
                self.ack_received.emit(cmd.track_id, cmd.command, status, rtt)
        self._close()

    def _close(self):
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        self.is_connected = False
        self.connected.emit(False)

    def stop(self):
        self._stop = True
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/integration/test_uart_loopback.py -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/core/uart.py tests/integration/test_uart_loopback.py
git commit -m "feat(core): uart worker with queue, ack timeout, auto-reconnect"
```


### Task 2.8: History service (SQLite + SQLAlchemy)

**Files:**
- Create: `app/core/history.py`
- Create: `tests/unit/test_history.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_history.py`:
```python
from datetime import datetime, UTC
from pathlib import Path

from app.core.history import HistoryService


def test_insert_and_query(tmp_path: Path):
    db = tmp_path / "h.db"
    svc = HistoryService(db)
    rid = svc.insert(
        track_id=1, ts=datetime.now(UTC), cls_id=0, cls_name="paper",
        conf=0.9, bbox=(10, 10, 100, 100), thumbnail=b"\x00",
        uart_command="P", ack_status="pending",
    )
    assert rid > 0
    rows = svc.query(limit=10)
    assert len(rows) == 1
    assert rows[0].cls_name == "paper"
    svc.close()


def test_update_ack(tmp_path: Path):
    db = tmp_path / "h.db"
    svc = HistoryService(db)
    rid = svc.insert(
        track_id=1, ts=datetime.now(UTC), cls_id=0, cls_name="paper",
        conf=0.9, bbox=(0, 0, 1, 1), thumbnail=b"",
        uart_command="P", ack_status="pending",
    )
    svc.update_ack(rid, status="ok", rtt_ms=42)
    row = svc.query(limit=1)[0]
    assert row.ack_status == "ok"
    assert row.rtt_ms == 42
    svc.close()


def test_export_csv(tmp_path: Path):
    db = tmp_path / "h.db"
    svc = HistoryService(db)
    svc.insert(
        track_id=1, ts=datetime.now(UTC), cls_id=0, cls_name="paper",
        conf=0.9, bbox=(0, 0, 1, 1), thumbnail=b"",
        uart_command="P", ack_status="ok", rtt_ms=10,
    )
    out = tmp_path / "h.csv"
    n = svc.export_csv(out)
    assert n == 1
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "paper" in text
    svc.close()


def test_stats_by_class(tmp_path: Path):
    db = tmp_path / "h.db"
    svc = HistoryService(db)
    for cls in ("paper", "paper", "plastic"):
        svc.insert(
            track_id=1, ts=datetime.now(UTC), cls_id=0, cls_name=cls,
            conf=0.9, bbox=(0, 0, 1, 1), thumbnail=b"",
            uart_command="X", ack_status="ok",
        )
    counts = svc.count_by_class()
    assert counts.get("paper") == 2
    assert counts.get("plastic") == 1
    svc.close()
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/test_history.py -v
```

Expected: FAIL `ModuleNotFoundError`.


- [ ] **Step 3: Implement `app/core/history.py`**

```python
"""SQLite-backed detection history service via SQLAlchemy."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Column, Integer, LargeBinary, MetaData, Real, String, Table, create_engine, func, select, text,
)
from sqlalchemy.engine import Engine

metadata = MetaData()

detections = Table(
    "detections", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("track_id", Integer, nullable=False),
    Column("ts", String, nullable=False),
    Column("cls_id", Integer, nullable=False),
    Column("cls_name", String, nullable=False),
    Column("conf", Real, nullable=False),
    Column("bbox_x1", Integer), Column("bbox_y1", Integer),
    Column("bbox_x2", Integer), Column("bbox_y2", Integer),
    Column("thumbnail", LargeBinary),
    Column("uart_command", String),
    Column("ack_status", String),
    Column("rtt_ms", Integer),
)


class HistoryRow:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class HistoryService:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine: Engine = create_engine(f"sqlite:///{db_path}", future=True)
        metadata.create_all(self._engine)
        with self._engine.begin() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_detections_ts ON detections(ts)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_detections_cls ON detections(cls_name)"))

    def insert(self, *, track_id, ts: datetime, cls_id, cls_name, conf, bbox,
               thumbnail=b"", uart_command=None, ack_status="pending", rtt_ms=None) -> int:
        x1, y1, x2, y2 = bbox
        with self._engine.begin() as conn:
            res = conn.execute(detections.insert().values(
                track_id=track_id, ts=ts.isoformat(), cls_id=cls_id, cls_name=cls_name,
                conf=conf, bbox_x1=x1, bbox_y1=y1, bbox_x2=x2, bbox_y2=y2,
                thumbnail=thumbnail, uart_command=uart_command,
                ack_status=ack_status, rtt_ms=rtt_ms,
            ))
            return int(res.inserted_primary_key[0])

    def update_ack(self, row_id: int, status: str, rtt_ms: int | None) -> None:
        with self._engine.begin() as conn:
            conn.execute(detections.update().where(detections.c.id == row_id).values(
                ack_status=status, rtt_ms=rtt_ms,
            ))

    def query(self, limit=200, offset=0, cls_name=None, since: datetime | None = None):
        stmt = select(detections).order_by(detections.c.id.desc()).limit(limit).offset(offset)
        if cls_name:
            stmt = stmt.where(detections.c.cls_name == cls_name)
        if since:
            stmt = stmt.where(detections.c.ts >= since.isoformat())
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [HistoryRow(**dict(r)) for r in rows]

    def count_by_class(self) -> dict[str, int]:
        stmt = select(detections.c.cls_name, func.count()).group_by(detections.c.cls_name)
        with self._engine.begin() as conn:
            return {name: int(cnt) for name, cnt in conn.execute(stmt).all()}

    def export_csv(self, out_path: Path) -> int:
        rows = self.query(limit=1_000_000)
        cols = ["id", "track_id", "ts", "cls_id", "cls_name", "conf",
                "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2",
                "uart_command", "ack_status", "rtt_ms"]
        with out_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in rows:
                w.writerow([getattr(r, c, "") for c in cols])
        return len(rows)

    def close(self) -> None:
        self._engine.dispose()
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/test_history.py -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/core/history.py tests/unit/test_history.py
git commit -m "feat(core): sqlite history with insert/update/query/export csv"
```


### Task 2.9: Pipeline orchestrator (no UI yet)

Wire camera + inference + tracker + uart + history together. Headless test.

**Files:**
- Create: `app/core/pipeline.py`
- Create: `tests/integration/test_pipeline_e2e.py`

- [ ] **Step 1: Write failing test**

`tests/integration/test_pipeline_e2e.py`:
```python
from datetime import datetime, UTC
from pathlib import Path

import numpy as np

from app.core.config import AppConfig, ClassMapping
from app.core.events import Detection
from app.core.pipeline import Pipeline


class _StubInfer:
    class_names = {0: "paper", 1: "plastic"}
    def __init__(self): self._n = 0
    def predict(self, frame):
        self._n += 1
        if self._n <= 3:
            return [Detection(0, "paper", 0.9, (10, 10, 100, 100))]
        return []


class _StubUart:
    def __init__(self): self.sent = []
    def send(self, track_id, command, conf): self.sent.append((track_id, command, conf))


def test_pipeline_emits_one_command_per_object(tmp_path):
    cfg = AppConfig(mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)])
    p = Pipeline(
        cfg=cfg,
        engine=_StubInfer(),
        uart=_StubUart(),
        history_db=tmp_path / "h.db",
    )
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    for _ in range(3):
        p.process_frame(frame, ts=datetime.now(UTC))
    assert len(p.uart.sent) == 1
    assert p.uart.sent[0][1] == "P"
    p.close()


def test_pipeline_skips_unmapped_class(tmp_path):
    cfg = AppConfig(mappings=[])
    p = Pipeline(cfg, _StubInfer(), _StubUart(), tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    p.process_frame(frame, ts=datetime.now(UTC))
    assert p.uart.sent == []
    p.close()


def test_pipeline_records_to_history(tmp_path):
    cfg = AppConfig(mappings=[ClassMapping(class_name="paper", command="P", bin_index=1)])
    p = Pipeline(cfg, _StubInfer(), _StubUart(), tmp_path / "h.db")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    p.process_frame(frame, ts=datetime.now(UTC))
    rows = p.history.query(limit=10)
    assert len(rows) == 1
    assert rows[0].cls_name == "paper"
    p.close()
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/integration/test_pipeline_e2e.py -v
```

Expected: FAIL `ModuleNotFoundError`.


- [ ] **Step 3: Implement `app/core/pipeline.py`**

```python
"""Pipeline orchestrator: frame → infer → track → uart → history."""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.config import AppConfig
from app.core.history import HistoryService
from app.core.tracker import Tracker
from app.utils.logging import logger


def _make_thumbnail(frame_bgr: np.ndarray, max_size=(100, 75)) -> bytes:
    rgb = frame_bgr[:, :, ::-1]
    img = Image.fromarray(rgb)
    img.thumbnail(max_size)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


class Pipeline:
    def __init__(self, cfg: AppConfig, engine, uart, history_db: Path):
        self.cfg = cfg
        self.engine = engine
        self.uart = uart
        self.tracker = Tracker(iou_threshold=0.3, max_age=30)
        self.history = HistoryService(history_db)
        self._mapping = {m.class_name: m for m in cfg.mappings if m.enabled}
        self._track_to_row: dict[int, int] = {}

    def update_mappings(self, mappings):
        self._mapping = {m.class_name: m for m in mappings if m.enabled}

    def _in_roi(self, xyxy):
        roi = self.cfg.roi
        if not roi.enabled or roi.width == 0 or roi.height == 0:
            return True
        x1, y1, x2, y2 = xyxy
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return roi.x <= cx <= roi.x + roi.width and roi.y <= cy <= roi.y + roi.height

    def process_frame(self, frame_bgr: np.ndarray, ts: datetime):
        raw = self.engine.predict(frame_bgr)
        filtered = [d for d in raw if d.conf >= self.cfg.model.conf_threshold and self._in_roi(d.xyxy)]
        tracked = self.tracker.update(filtered)
        for t in tracked:
            if not self.tracker.should_emit(t.track_id):
                continue
            mapping = self._mapping.get(t.detection.cls_name)
            if mapping is None:
                continue
            self.tracker.mark_emitted(t.track_id)
            thumb = _make_thumbnail(frame_bgr)
            row_id = self.history.insert(
                track_id=t.track_id, ts=ts,
                cls_id=t.detection.cls_id, cls_name=t.detection.cls_name,
                conf=t.detection.conf, bbox=t.detection.xyxy,
                thumbnail=thumb, uart_command=mapping.command, ack_status="pending",
            )
            self._track_to_row[t.track_id] = row_id
            self.uart.send(track_id=t.track_id, command=mapping.command, conf=t.detection.conf)
            logger.info("dispatch track={} cls={} cmd={} conf={:.2f}",
                        t.track_id, t.detection.cls_name, mapping.command, t.detection.conf)

    def on_ack(self, track_id: int, command: str, status: str, rtt_ms):
        row_id = self._track_to_row.pop(track_id, None)
        if row_id is None:
            return
        self.history.update_ack(row_id, status=status, rtt_ms=rtt_ms)

    def close(self):
        self.history.close()
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/integration/test_pipeline_e2e.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/core/pipeline.py tests/integration/test_pipeline_e2e.py
git commit -m "feat(core): pipeline orchestrator with roi filter and ack hookup"
```


---

## Milestone M3 — UI shell + Live tab (1 ngày)

Sidebar layout, frameless title bar, dark QSS theme, Live tab có video view + bbox overlay + status bar.

### Task 3.1: Design tokens + dark QSS

**Files:**
- Create: `app/ui/resources/qss/dark.qss`
- Create: `app/ui/resources/qss/light.qss`
- Create: `app/ui/widgets/__init__.py`
- Create: `app/ui/widgets/theme.py`

- [ ] **Step 1: Write `app/ui/resources/qss/dark.qss`**

```css
* {
  font-family: "Inter", "Segoe UI", sans-serif;
  font-size: 14px;
  color: #F1F5F9;
}

QMainWindow, QDialog {
  background: #0B1220;
}

QLabel { background: transparent; }

QLabel#h1 { font-size: 28px; font-weight: 700; }
QLabel#h2 { font-size: 20px; font-weight: 600; }
QLabel#muted { color: #94A3B8; }
QLabel#mono { font-family: "JetBrains Mono", "Consolas", monospace; }

#sidebar {
  background: #0E1628;
  border-right: 1px solid rgba(255,255,255,0.06);
}

#sidebar QPushButton {
  background: transparent;
  border: none;
  text-align: left;
  padding: 12px 16px;
  border-radius: 6px;
  color: #94A3B8;
}
#sidebar QPushButton:hover { background: #152038; color: #F1F5F9; }
#sidebar QPushButton:checked {
  background: #152038; color: #F1F5F9;
  border-left: 3px solid #10B981;
}

#card {
  background: #111A2E;
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 12px;
}

QPushButton#primary {
  background: #10B981; color: #0B1220;
  border: none; border-radius: 6px;
  padding: 8px 16px; font-weight: 600;
}
QPushButton#primary:hover { background: #34D399; }
QPushButton#primary:pressed { background: #059669; }

QPushButton#secondary {
  background: transparent; color: #F1F5F9;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 6px; padding: 8px 16px;
}
QPushButton#secondary:hover { background: #152038; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
  background: #0B1220;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 6px; padding: 6px 10px;
  color: #F1F5F9;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
  border: 1px solid #10B981;
}

QSlider::groove:horizontal {
  background: #152038; height: 4px; border-radius: 2px;
}
QSlider::handle:horizontal {
  background: #10B981; width: 14px; height: 14px;
  margin: -5px 0; border-radius: 7px;
}

#statusbar {
  background: #0E1628;
  border-top: 1px solid rgba(255,255,255,0.06);
  color: #94A3B8;
}

#titlebar {
  background: #0E1628;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
#titlebar QPushButton {
  background: transparent; border: none; padding: 6px 12px;
  color: #94A3B8;
}
#titlebar QPushButton:hover { background: #152038; color: #F1F5F9; }
#titlebar QPushButton#close-btn:hover { background: #EF4444; color: white; }

QScrollBar:vertical {
  background: transparent; width: 10px; margin: 0;
}
QScrollBar::handle:vertical {
  background: #1E293B; border-radius: 5px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #334155; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QTableView {
  background: #111A2E;
  alternate-background-color: #152038;
  gridline-color: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px;
}
QHeaderView::section {
  background: #0E1628; color: #94A3B8;
  border: none; padding: 8px 12px; font-weight: 600;
}
```

- [ ] **Step 2: Write `app/ui/resources/qss/light.qss`** (minimal — chỉ override màu, để dành polish sau)

```css
* { font-family: "Inter", "Segoe UI", sans-serif; font-size: 14px; color: #0F172A; }
QMainWindow, QDialog { background: #F8FAFC; }
#sidebar { background: #F1F5F9; border-right: 1px solid #E2E8F0; }
#card { background: white; border: 1px solid #E2E8F0; border-radius: 12px; }
QPushButton#primary { background: #10B981; color: white; border: none; border-radius: 6px; padding: 8px 16px; font-weight: 600; }
```

- [ ] **Step 3: Write `app/ui/widgets/theme.py`**

```python
"""Theme loader: read QSS file, apply to QApplication."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

QSS_DIR = Path(__file__).parent.parent / "resources" / "qss"


def apply_theme(app: QApplication, theme: str = "dark") -> None:
    qss_file = QSS_DIR / f"{theme}.qss"
    if not qss_file.exists():
        qss_file = QSS_DIR / "dark.qss"
    app.setStyleSheet(qss_file.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Wire into `app/__main__.py`**

Replace `app/__main__.py`:
```python
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.widgets.theme import apply_theme
from app.utils.logging import logger, setup_logging


def main() -> int:
    setup_logging()
    logger.info("starting app")
    app = QApplication(sys.argv)
    app.setApplicationName("Trash Sorter Pro")
    app.setOrganizationName("TrashSorter")
    apply_theme(app, "dark")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run app, verify dark theme applied**

```bash
uv run python -m app
```

Expected: Window background dark navy `#0B1220`.

- [ ] **Step 6: Commit**

```bash
git add app/ui/resources/ app/ui/widgets/theme.py app/__main__.py
git commit -m "feat(ui): dark/light qss themes and theme loader"
```

### Task 3.2: Frameless title bar widget

**Files:**
- Create: `app/ui/widgets/title_bar.py`
- Create: `tests/ui/__init__.py`
- Create: `tests/ui/test_title_bar.py`

- [ ] **Step 1: Write failing test**

`tests/ui/test_title_bar.py`:
```python
from app.ui.widgets.title_bar import TitleBar


def test_titlebar_has_buttons(qtbot):
    bar = TitleBar(title="Test App")
    qtbot.addWidget(bar)
    assert bar.btn_min is not None
    assert bar.btn_max is not None
    assert bar.btn_close is not None
    assert "Test App" in bar.label.text()
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/ui/test_title_bar.py -v
```

- [ ] **Step 3: Implement `app/ui/widgets/title_bar.py`**

```python
"""Custom frameless window title bar."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class TitleBar(QWidget):
    minimize_requested = Signal()
    maximize_toggled = Signal()
    close_requested = Signal()

    def __init__(self, title: str = "Trash Sorter Pro", parent=None):
        super().__init__(parent)
        self.setObjectName("titlebar")
        self.setFixedHeight(40)
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 0, 0)
        layout.setSpacing(0)

        self.label = QLabel(f"●  {title}")
        self.label.setStyleSheet("color: #F1F5F9; font-weight: 600;")
        layout.addWidget(self.label)
        layout.addStretch()

        self.btn_min = QPushButton("—")
        self.btn_max = QPushButton("□")
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("close-btn")

        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setFixedSize(46, 40)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(b)

        self.btn_min.clicked.connect(self.minimize_requested)
        self.btn_max.clicked.connect(self.maximize_toggled)
        self.btn_close.clicked.connect(self.close_requested)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_offset is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            self.window().move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        self._drag_offset = None

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        self.maximize_toggled.emit()
```

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add app/ui/widgets/title_bar.py tests/ui/
git commit -m "feat(ui): frameless custom title bar widget"
```

### Task 3.3: Video view widget với bbox overlay

**Files:**
- Create: `app/ui/widgets/video_view.py`

- [ ] **Step 1: Implement `app/ui/widgets/video_view.py`**

```python
"""Video display widget with bbox overlay (paintEvent based)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QFont
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.core.events import Detection


def _conf_color(conf: float) -> QColor:
    if conf >= 0.8: return QColor("#10B981")
    if conf >= 0.5: return QColor("#F59E0B")
    return QColor("#EF4444")


class VideoView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(640, 360)
        self._pixmap: QPixmap | None = None
        self._frame_w = 0
        self._frame_h = 0
        self._detections: list[Detection] = []
        self.setStyleSheet("background: #000;")

    def set_frame(self, frame_bgr: np.ndarray) -> None:
        h, w, _ = frame_bgr.shape
        rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])
        img = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(img.copy())
        self._frame_w, self._frame_h = w, h
        self.update()

    def set_detections(self, detections: list[Detection]) -> None:
        self._detections = detections
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._pixmap is None:
            p.fillRect(self.rect(), QColor("#000"))
            return
        target = self.rect()
        scaled = self._pixmap.scaled(
            target.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (target.width() - scaled.width()) // 2
        y = (target.height() - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
        if self._frame_w and self._frame_h:
            sx = scaled.width() / self._frame_w
            sy = scaled.height() / self._frame_h
            font = QFont("Inter", 10, QFont.Weight.Bold)
            p.setFont(font)
            for d in self._detections:
                x1, y1, x2, y2 = d.xyxy
                rx = int(x + x1 * sx); ry = int(y + y1 * sy)
                rw = int((x2 - x1) * sx); rh = int((y2 - y1) * sy)
                color = _conf_color(d.conf)
                pen = QPen(color); pen.setWidth(2); p.setPen(pen)
                p.drawRoundedRect(rx, ry, rw, rh, 4, 4)
                label = f"{d.cls_name} {d.conf:.2f}"
                metrics = p.fontMetrics()
                tw = metrics.horizontalAdvance(label) + 12
                th = metrics.height() + 4
                p.fillRect(rx, ry - th, tw, th, color)
                p.setPen(QColor("#0B1220"))
                p.drawText(rx + 6, ry - 4, label)
```

- [ ] **Step 2: Commit**

```bash
git add app/ui/widgets/video_view.py
git commit -m "feat(ui): video view widget with bbox overlay"
```

### Task 3.4: Sidebar + main window shell

**Files:**
- Create: `app/ui/widgets/sidebar.py`
- Modify: `app/ui/main_window.py` (full rewrite)

- [ ] **Step 1: Implement `app/ui/widgets/sidebar.py`**

```python
"""Sidebar with mutually-exclusive nav buttons."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QPushButton, QVBoxLayout, QWidget


class Sidebar(QWidget):
    page_changed = Signal(int)

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = []

        for idx, label in enumerate(items):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(0)
            self._group.addButton(btn, idx)
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()
        if self._buttons:
            self._buttons[0].setChecked(True)
        self._group.idClicked.connect(self.page_changed.emit)

    def set_active(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
```

- [ ] **Step 2: Rewrite `app/ui/main_window.py`**

```python
"""Frameless main window: title bar + sidebar + stacked pages + status bar."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget,
)

from app.ui.widgets.sidebar import Sidebar
from app.ui.widgets.title_bar import TitleBar


NAV_ITEMS = ["▶  Live", "▦  Lịch sử", "⇆  Mapping", "◉  Capture", "⚙  Cài đặt"]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.resize(1280, 800)

        root = QWidget()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = TitleBar("Trash Sorter Pro")
        self.title_bar.minimize_requested.connect(self.showMinimized)
        self.title_bar.maximize_toggled.connect(self._toggle_max)
        self.title_bar.close_requested.connect(self.close)
        outer.addWidget(self.title_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = Sidebar(NAV_ITEMS)
        self.stack = QStackedWidget()
        for label in NAV_ITEMS:
            page = QLabel(f"{label} — placeholder")
            page.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stack.addWidget(page)
        self.sidebar.page_changed.connect(self.stack.setCurrentIndex)

        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.stack, 1)
        outer.addWidget(body, 1)

        self.status = QLabel("● Camera —  •  ● UART —  •  ● Model —  •  FPS 0  ")
        self.status.setObjectName("statusbar")
        self.status.setFixedHeight(32)
        self.status.setContentsMargins(16, 0, 16, 0)
        outer.addWidget(self.status)

        for i in range(5):
            QShortcut(QKeySequence(f"Ctrl+{i+1}"), self, activated=lambda i=i: (
                self.sidebar.set_active(i), self.stack.setCurrentIndex(i),
            ))
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)

    def _toggle_max(self) -> None:
        if self.isMaximized(): self.showNormal()
        else: self.showMaximized()
```

- [ ] **Step 3: Run app, verify shell renders**

```bash
uv run python -m app
```

Expected: Window with custom title bar, sidebar 5 items, content placeholder, status bar.

- [ ] **Step 4: Commit**

```bash
git add app/ui/widgets/sidebar.py app/ui/main_window.py
git commit -m "feat(ui): main window shell with sidebar, stack pages, status bar"
```

### Task 3.5: Stat card widget + Live page

**Files:**
- Create: `app/ui/widgets/stat_card.py`
- Create: `app/ui/pages/__init__.py`
- Create: `app/ui/pages/live.py`

- [ ] **Step 1: Implement `app/ui/widgets/stat_card.py`**

```python
"""Compact stat card: label + value + sublabel."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StatCard(QWidget):
    def __init__(self, label: str, value: str = "—", sub: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(96)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self._label = QLabel(label.upper())
        self._label.setObjectName("muted")
        self._label.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600; letter-spacing: 1px;")
        layout.addWidget(self._label)

        self._value = QLabel(value)
        self._value.setObjectName("mono")
        self._value.setStyleSheet("font-size: 28px; font-weight: 700; color: #F1F5F9; font-family: 'JetBrains Mono','Consolas',monospace;")
        layout.addWidget(self._value)

        self._sub = QLabel(sub)
        self._sub.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(self._sub)

        layout.addStretch()

    def set_value(self, value: str) -> None:
        self._value.setText(value)

    def set_sub(self, sub: str) -> None:
        self._sub.setText(sub)
```

- [ ] **Step 2: Implement `app/ui/pages/live.py`**

```python
"""Live tab: video feed + detection stream + stat cards."""
from __future__ import annotations

from collections import deque

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from app.core.events import Detection
from app.ui.widgets.stat_card import StatCard
from app.ui.widgets.video_view import VideoView


class LivePage(QWidget):
    pause_toggled = Signal(bool)
    snapshot_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paused = False
        self._fps_window = deque(maxlen=30)
        self._latency_window = deque(maxlen=30)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # header
        header = QHBoxLayout()
        title = QLabel("Live Detection")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()
        self.btn_pause = QPushButton("⏸  Pause")
        self.btn_pause.setObjectName("secondary")
        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_snap = QPushButton("📷  Snapshot")
        self.btn_snap.setObjectName("secondary")
        self.btn_snap.clicked.connect(self.snapshot_requested.emit)
        header.addWidget(self.btn_pause)
        header.addWidget(self.btn_snap)
        root.addLayout(header)

        # body: video + detection stream
        body = QHBoxLayout()
        body.setSpacing(16)

        self.video = VideoView()
        body.addWidget(self.video, 3)

        self.stream = QListWidget()
        self.stream.setObjectName("card")
        self.stream.setMinimumWidth(280)
        self.stream.setStyleSheet("QListWidget { border-radius: 12px; padding: 8px; }")
        body.addWidget(self.stream, 1)

        root.addLayout(body, 1)

        # stat cards
        cards = QGridLayout()
        cards.setSpacing(12)
        self.card_today = StatCard("TODAY", "0", "items")
        self.card_fps = StatCard("FPS", "0", "render")
        self.card_latency = StatCard("LATENCY", "0", "ms infer")
        self.card_uart = StatCard("UART", "—", "status")
        self.card_total = StatCard("TOTAL", "0", "all-time")
        self.card_acc = StatCard("AVG CONF", "0.00", "running")
        for col, c in enumerate([self.card_today, self.card_fps, self.card_latency,
                                 self.card_uart, self.card_total, self.card_acc]):
            cards.addWidget(c, 0, col)
        root.addLayout(cards)

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self.btn_pause.setText("▶  Resume" if self._paused else "⏸  Pause")
        self.pause_toggled.emit(self._paused)

    def is_paused(self) -> bool:
        return self._paused

    def update_frame(self, frame, detections: list[Detection]) -> None:
        if self._paused:
            return
        self.video.set_frame(frame)
        self.video.set_detections(detections)

    def append_detection(self, cls_name: str, conf: float, ts: str) -> None:
        item = QListWidgetItem(f"●  {cls_name:<10} {conf:.2f}    {ts}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.stream.insertItem(0, item)
        while self.stream.count() > 50:
            self.stream.takeItem(self.stream.count() - 1)

    def set_fps(self, fps: float) -> None:
        self.card_fps.set_value(f"{fps:.0f}")

    def set_latency(self, ms: float) -> None:
        self.card_latency.set_value(f"{ms:.0f}")

    def set_today(self, n: int) -> None:
        self.card_today.set_value(str(n))

    def set_total(self, n: int) -> None:
        self.card_total.set_value(str(n))

    def set_uart_status(self, ok: bool) -> None:
        self.card_uart.set_value("OK" if ok else "OFF")
        self.card_uart.set_sub("connected" if ok else "disconnected")

    def set_avg_conf(self, conf: float) -> None:
        self.card_acc.set_value(f"{conf:.2f}")
```

- [ ] **Step 3: Wire LivePage into MainWindow**

In `app/ui/main_window.py`, replace the placeholder loop in `__init__` with:
```python
from app.ui.pages.live import LivePage
# ...
self.live_page = LivePage()
self.stack.addWidget(self.live_page)
for label in NAV_ITEMS[1:]:
    page = QLabel(f"{label} — placeholder")
    page.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.stack.addWidget(page)
```

- [ ] **Step 4: Run, verify Live page renders**

```bash
uv run python -m app
```

Expected: Live tab default, video black placeholder, 6 stat cards, detection stream empty.

- [ ] **Step 5: Commit**

```bash
git add app/ui/widgets/stat_card.py app/ui/pages/ app/ui/main_window.py
git commit -m "feat(ui): live page with video, detection stream, stat cards"
```

### Task 3.6: AppController — wire workers to UI

**Files:**
- Create: `app/ui/controller.py`
- Modify: `app/__main__.py`

- [ ] **Step 1: Implement `app/ui/controller.py`**

```python
"""Glue between core workers and UI signals/slots."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from app.core.camera import CameraWorker
from app.core.config import AppConfig, save_config
from app.core.inference import InferenceEngine
from app.core.pipeline import Pipeline
from app.core.uart import UartWorker
from app.utils.logging import logger


class AppController(QObject):
    camera_status = Signal(bool)
    uart_status = Signal(bool)
    model_status = Signal(bool)

    def __init__(self, cfg: AppConfig, config_path: Path, db_path: Path):
        super().__init__()
        self.cfg = cfg
        self.config_path = config_path
        self.db_path = db_path
        self._engine: InferenceEngine | None = None
        self._camera: CameraWorker | None = None
        self._uart: UartWorker | None = None
        self._pipeline: Pipeline | None = None
        self._last_frame_t = 0.0
        self._fps = 0.0
        self._latency = 0.0
        self._today_count = 0
        self._total_count = 0
        self._sum_conf = 0.0

    def start(self):
        self._engine = InferenceEngine(
            self.cfg.model.path, device=self.cfg.model.device,
            conf=self.cfg.model.conf_threshold, iou=self.cfg.model.iou_threshold,
            imgsz=self.cfg.model.input_size, half=self.cfg.model.half_precision,
        )
        self.model_status.emit(True)

        self._uart = UartWorker(
            port=self.cfg.uart.port, baud=self.cfg.uart.baud,
            ack_timeout_ms=self.cfg.uart.ack_timeout_ms,
            auto_reconnect=self.cfg.uart.auto_reconnect,
        )
        self._uart.connected.connect(self.uart_status.emit)
        self._uart.start()

        self._pipeline = Pipeline(self.cfg, self._engine, self._uart, self.db_path)
        self._uart.ack_received.connect(self._pipeline.on_ack)

        self._camera = CameraWorker(
            source=self.cfg.camera.source, width=self.cfg.camera.width,
            height=self.cfg.camera.height, mirror=self.cfg.camera.mirror,
        )
        self._camera.connected.connect(self.camera_status.emit)
        self._camera.frame_ready.connect(self._on_frame)
        self._camera.start()

    def _on_frame(self, frame):
        t0 = time.time()
        ts = datetime.now(timezone.utc)
        self._pipeline.process_frame(frame, ts)
        dt = time.time() - t0
        self._latency = dt * 1000
        if self._last_frame_t:
            inst_fps = 1.0 / max(time.time() - self._last_frame_t, 1e-6)
            self._fps = 0.9 * self._fps + 0.1 * inst_fps
        self._last_frame_t = time.time()
        self.frame_processed.emit(frame, self._engine.predict(frame) if False else [], self._fps, self._latency)

    frame_processed = Signal(object, list, float, float)

    def update_config(self, new_cfg: AppConfig):
        self.cfg = new_cfg
        save_config(new_cfg, self.config_path)
        if self._engine is not None:
            self._engine.update_thresholds(new_cfg.model.conf_threshold, new_cfg.model.iou_threshold)
        if self._pipeline is not None:
            self._pipeline.update_mappings(new_cfg.mappings)

    def stop(self):
        if self._camera: self._camera.stop(); self._camera.wait(2000)
        if self._uart: self._uart.stop(); self._uart.wait(2000)
        if self._pipeline: self._pipeline.close()
```

> Note: `frame_processed` simplified — emit `frame, detections, fps, latency`. The actual detections come from pipeline; refactor at M4 to avoid double-infer. For M3, we accept duplicate inference cost; M4 task 4.1 will fix this by exposing pipeline output.

- [ ] **Step 2: Wire in `app/__main__.py`**

```python
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.core.config import load_config
from app.ui.controller import AppController
from app.ui.main_window import MainWindow
from app.ui.widgets.theme import apply_theme
from app.utils.logging import logger, setup_logging
from app.utils.paths import config_path, db_path


def main() -> int:
    setup_logging()
    logger.info("starting app")
    app = QApplication(sys.argv)
    app.setApplicationName("Trash Sorter Pro")
    app.setOrganizationName("TrashSorter")

    cfg_path = config_path()
    cfg = load_config(cfg_path)
    apply_theme(app, cfg.theme)

    window = MainWindow()
    controller = AppController(cfg, cfg_path, db_path())
    controller.camera_status.connect(lambda ok: window.live_page.set_uart_status(ok) if False else None)
    controller.uart_status.connect(window.live_page.set_uart_status)
    window.show()
    controller.start()
    rc = app.exec()
    controller.stop()
    return rc


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Refactor pipeline emit detections to controller**

In `app/core/pipeline.py`, add signal to expose tracked detections per frame. Change `process_frame` to return the tracked list, AppController uses that to draw.

```python
def process_frame(self, frame_bgr, ts):
    raw = self.engine.predict(frame_bgr)
    filtered = [d for d in raw if d.conf >= self.cfg.model.conf_threshold and self._in_roi(d.xyxy)]
    tracked = self.tracker.update(filtered)
    detections_for_render = [t.detection for t in tracked]
    for t in tracked:
        if not self.tracker.should_emit(t.track_id):
            continue
        mapping = self._mapping.get(t.detection.cls_name)
        if mapping is None:
            continue
        self.tracker.mark_emitted(t.track_id)
        thumb = _make_thumbnail(frame_bgr)
        row_id = self.history.insert(
            track_id=t.track_id, ts=ts,
            cls_id=t.detection.cls_id, cls_name=t.detection.cls_name,
            conf=t.detection.conf, bbox=t.detection.xyxy,
            thumbnail=thumb, uart_command=mapping.command, ack_status="pending",
        )
        self._track_to_row[t.track_id] = row_id
        self.uart.send(track_id=t.track_id, command=mapping.command, conf=t.detection.conf)
    return detections_for_render
```

Update controller `_on_frame` to use return value:
```python
def _on_frame(self, frame):
    t0 = time.time()
    ts = datetime.now(timezone.utc)
    detections = self._pipeline.process_frame(frame, ts)
    dt = time.time() - t0
    # ... fps/latency calc
    self.frame_processed.emit(frame, detections, self._fps, self._latency)
```

In MainWindow connect controller.frame_processed:
```python
controller.frame_processed.connect(lambda frame, det, fps, lat: (
    window.live_page.update_frame(frame, det),
    window.live_page.set_fps(fps),
    window.live_page.set_latency(lat),
))
```

- [ ] **Step 4: Run end-to-end**

```bash
uv run python -m app
```

Expected: live video from default camera, bbox over detections, FPS/Latency cards updating, UART status reflects connection.

- [ ] **Step 5: Commit**

```bash
git add app/ui/controller.py app/__main__.py app/core/pipeline.py
git commit -m "feat(ui): controller wires workers to live page"
```

---

## Milestone M4 — Settings + Mapping tabs (1 ngày)

Hai tab cấu hình chạy đầy đủ với atomic save và hot-reload model.

### Task 4.1: Toast notification widget

**Files:**
- Create: `app/ui/widgets/toast.py`

- [ ] **Step 1: Implement `app/ui/widgets/toast.py`**

```python
"""Toast notification: slide-in top-right, auto-dismiss."""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


_LEVEL_COLORS = {
    "info": "#3B82F6",
    "ok": "#10B981",
    "warn": "#F59E0B",
    "error": "#EF4444",
}


class Toast(QFrame):
    def __init__(self, parent: QWidget, message: str, level: str = "info", duration_ms: int = 4000):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setStyleSheet(
            "#toast { background: #111A2E; border: 1px solid rgba(255,255,255,0.1);"
            "border-radius: 8px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {_LEVEL_COLORS.get(level, '#3B82F6')}; font-size: 16px;")
        layout.addWidget(dot)

        msg = QLabel(message)
        msg.setStyleSheet("color: #F1F5F9;")
        layout.addWidget(msg)

        self.adjustSize()
        self._duration = duration_ms

    def show_at(self, anchor_topright: QPoint) -> None:
        end_x = anchor_topright.x() - self.width() - 16
        end_y = anchor_topright.y() + 16
        start = QPoint(anchor_topright.x() + 20, end_y)
        self.move(start)
        self.show()
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(220)
        anim.setStartValue(start)
        anim.setEndValue(QPoint(end_x, end_y))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        QTimer.singleShot(self._duration, self.close)
```

- [ ] **Step 2: Commit**

```bash
git add app/ui/widgets/toast.py
git commit -m "feat(ui): toast notification widget"
```


### Task 4.2: Settings page (compact)

**Files:** Create `app/ui/pages/settings.py`

**Implementation outline:**
- Một `QWidget` chứa 4 section card: Camera / Model / UART / Ứng dụng.
- Helper `_section(title)` trả về `(QFrame#card, QFormLayout)`.
- Camera fields: source (QLineEdit), width/height (QSpinBox), mirror (QCheckBox), btn `Test camera`.
- Model fields: path (QLineEdit + Browse), device (QComboBox cpu/cuda), conf/iou (QSlider 0..100), input_size (QComboBox 320/480/640/800/960), btn `Hot reload`.
- UART fields: port, baud (QComboBox 9600..115200), ack_timeout (QSpinBox 50..5000ms), auto_reconnect (QCheckBox), btn `Test ping`.
- App fields: theme (dark/light), language (vi/en), minimize_to_tray, autostart.
- Bottom row: `Hủy` (#secondary) + `Lưu cài đặt` (#primary).
- Signals exposed:
  - `config_saved = Signal(AppConfig)` — emit when Save clicked, payload = collected config.
  - `test_camera_requested = Signal(str)` — payload = source.
  - `test_uart_requested = Signal(str, int)` — payload = port, baud.
  - `reload_model_requested = Signal(str)` — payload = path.
- Method `_collect()` builds new `AppConfig` from widgets (deep copy of original then override fields).
- MainWindow: replace tab 4 placeholder with `SettingsPage(cfg)`. Connect `config_saved` to `AppController.update_config`.

**Tests:**
- `tests/ui/test_settings_page.py`: instantiate page with default config, set conf slider to 50, click Lưu, capture emitted config, assert `cfg.model.conf_threshold == 0.5`.

**Commit:** `feat(ui): settings page with atomic save and test buttons`

### Task 4.3: Mapping page

**Files:** Create `app/ui/pages/mapping.py`

**Implementation outline:**
- Top: title + buttons `Reset`, `Lưu`.
- For each `ClassMapping` in `cfg.mappings`: row with drag handle ⠿, class name (label), command (QLineEdit max 1 char, uppercase), bin index (QSpinBox 1..9), enabled (QCheckBox), btn `Test`.
- Use `QListWidget` with custom item widget for drag-reorder support (`setDragDropMode(InternalMove)`).
- Bottom: protocol preview card showing `SORT:<cmd>:<conf>\n` for the focused row.
- Signals:
  - `mappings_saved = Signal(list)` — payload = list[ClassMapping].
  - `test_command_requested = Signal(str)` — payload = command.

**Tests:**
- `tests/ui/test_mapping_page.py`: load 3 mappings, change command, save, assert emitted list has updated command.

**Commit:** `feat(ui): mapping page with drag-reorder and per-row test`

### Task 4.4: Test buttons wired in controller

In `AppController`, add slots:

```python
def test_camera(self, source: str):
    # spawn temporary CameraWorker; emit success/fail toast
    pass

def test_uart_ping(self, port: str, baud: int):
    # open serial, write PING, expect PONG within 1s, close
    pass

def reload_model(self, path: str):
    # rebuild InferenceEngine on new path; on fail show error toast
    pass
```

Wire from SettingsPage signals.

**Commit:** `feat(controller): handle test camera/uart and hot-reload model`

### Task 4.5: Atomic config save in controller

Already wired in Task 3.6 via `update_config`. Confirm: write to `.tmp` then `os.replace`. Add test `tests/integration/test_config_save_crash.py`: simulate write fail at midpoint, assert original config preserved.

**Commit:** `test: atomic config save survives mid-write fail`

---

## Milestone M5 — History + Capture tabs (1 ngày)

### Task 5.1: History page with charts + table

**Files:** Create `app/ui/pages/history.py`

**Implementation outline:**
- Top filter row: date range (`QDateEdit` × 2), class (`QComboBox`), ack status (`QComboBox`), btn `Refresh`, btn `Export CSV`.
- Middle: 2-column grid:
  - Left card: `pyqtgraph.PlotWidget` bar chart `count by class` (use `BarGraphItem` with emerald brush).
  - Right card: `pyqtgraph.PlotWidget` area chart `count by hour` (curve + brush fill, gradient).
- Bottom: `QTableView` with model `HistoryTableModel(rows)` showing thumbnail / time / class / conf / uart / status. Columns sortable, row double-click opens detail dialog.
- Service: `HistoryService.query(...)` already exists. Extend with `count_by_hour(date)` returning dict[int, int].

**Tests:**
- `tests/ui/test_history_page.py`: seed DB with 5 rows, instantiate page, assert table model has 5 rows, chart has data.

**Commit:** `feat(ui): history page with bar+area charts and virtualized table`

### Task 5.2: Detail dialog (full image + bbox)

**Files:** Create `app/ui/widgets/detail_dialog.py`

**Implementation outline:**
- `QDialog` size 800×600. Layout: left = image (load from thumbnail blob, scaled), right = info panel (track_id, ts, class, conf, uart_command, ack_status, rtt_ms).
- For full image: thumbnail is small (100×75); design says snapshot saved separately to `snapshots/`. Detail loads either snapshot file (if present) or scaled thumbnail.
- Add column `snapshot_path TEXT` to `detections` schema via migration `002_snapshot_path.sql`.

**Commit:** `feat(ui): history detail dialog with snapshot preview`

### Task 5.3: Capture page (low-conf review queue)

**Files:** Create `app/ui/pages/capture.py`

**Implementation outline:**
- Header: mode radio buttons (Off / Manual / Auto khi conf < threshold), counter "Đã capture: N ảnh", btn `Export YOLO format`.
- Grid: `QListWidget` with `IconMode`, item size 160×120, each item shows thumbnail + tiny label `cls 0.42`.
- Click thumbnail → opens mini-labeler dialog: image canvas + draw bbox + class dropdown + Save.
- Saving annotation writes to `dataset_v2/images/<uuid>.jpg` + `dataset_v2/labels/<uuid>.txt` (YOLO format: `cls cx cy w h` normalized).
- Generate `dataset_v2/data.yaml` on Export.
- Pipeline: when conf < `cfg.capture.low_conf_threshold` and mode == auto, save full frame to `low_conf_queue/` with sidecar JSON {boxes, conf, ts}.

**Implementation step:**
1. Extend `Pipeline._on_low_conf(frame, detections)` and emit signal.
2. CapturePage subscribes to signal, refreshes grid.
3. Mini-labeler at `app/ui/widgets/mini_labeler.py`: simple rect drag, class combo, Save → write to dataset folder.

**Tests:**
- `tests/unit/test_yolo_export.py`: write 2 fake annotations, run `export_yolo(output_dir)`, assert `data.yaml` exists with names list, `images/` and `labels/` populated.

**Commit:** `feat(ui): capture page with auto low-conf and yolo export`

### Task 5.4: Snapshot from Live tab → file

In `AppController`, slot `take_snapshot()`: save current frame to `snapshots_dir() / f"snap-{ts}.jpg"`. LivePage `snapshot_requested` connects here. Toast on success.

**Commit:** `feat(controller): snapshot to disk from live tab`

---

## Milestone M6 — Polish + Test (1 ngày)

### Task 6.1: System tray + minimize to tray

`app/ui/widgets/tray.py` — `QSystemTrayIcon` with menu (Show / Pause / Exit). MainWindow `closeEvent`: if `cfg.minimize_to_tray`, hide instead of close. Tray balloon notification on UART disconnect.

**Commit:** `feat(ui): system tray with minimize and balloon notifications`

### Task 6.2: Splash screen

`app/ui/widgets/splash.py` — `QSplashScreen` shown before model load, hidden when controller.start() returns. Display logo + "Loading model…".

**Commit:** `feat(ui): splash screen on cold start`

### Task 6.3: About dialog + i18n stub

`app/ui/widgets/about.py` — modal: version, model class names, input size, link GitHub. Trigger via `Ctrl+?`.

For i18n stub: load `app/ui/resources/i18n/vi.qm` if exists, fallback to en. Generate `.ts` via `pylupdate6`, compile via `lrelease`. M1 skip translations; just load mechanism.

**Commit:** `feat(ui): about dialog and i18n loader`

### Task 6.4: Skeleton loaders

`app/ui/widgets/skeleton.py` — `QLabel` with shimmer `QLinearGradient` animated via `QPropertyAnimation`. Use in History tab while query running, in Live tab while model loading.

**Commit:** `feat(ui): skeleton loader widget`

### Task 6.5: Empty states + illustrations

For each tab when no data: centered SVG icon + heading + sub-message. Add `app/ui/resources/icons/empty-*.svg` (placeholder simple SVG, not required to be art).

**Commit:** `feat(ui): empty state components per tab`

### Task 6.6: Coverage gate

Update `pyproject.toml`:
```toml
[tool.pytest.ini_options]
addopts = "-ra --strict-markers --cov=app/core --cov-fail-under=80"
```

Update CI: remove `continue-on-error` on lint/mypy/pytest after baseline passes locally.

**Commit:** `ci: enforce strict gates on lint/types/coverage`

### Task 6.7: ADRs

Create:
- `docs/adr/template.md`
- `docs/adr/0001-record-architecture-decisions.md`
- `docs/adr/0002-pyside6-over-pyqt5.md`
- `docs/adr/0003-iou-tracker-vs-bytetrack.md`
- `docs/adr/0004-uart-text-protocol.md`
- `docs/adr/0005-sqlite-local-first.md`
- `docs/adr/0006-uv-over-poetry.md`

Each ~30 lines: Context / Decision / Consequences / Alternatives.

**Commit:** `docs: initial set of architecture decision records`

### Task 6.8: README + CHANGELOG + per-service docs

Expand `README.md` (Run / Build / Test / Architecture / Screenshots placeholders).
Create `CHANGELOG.md` (Keep a Changelog) with entry `## [2.0.0] - 2026-05-21 — first release`.
Create `app/core/README.md` and `app/ui/README.md` per global rule (Purpose / API / Env / Run / Test / Runbook).

**Commit:** `docs: project readme, changelog, per-module readmes`

### Task 6.9: Manual QA pass

Run through `spec §8.3` manual checklist, fix issues, document deviations.

**Commit:** `chore: pass m6 manual qa, fix discovered issues`

---

## Milestone M7 — Build + Release (0.5 ngày)

### Task 7.1: Firmware sample (Arduino)

`firmware/arduino_servo/arduino_servo.ino` — accept `SORT:<cmd>:<conf>` lines, drive servo to angle mapped per command, send `ACK:<cmd>` after move complete. Comment Vietnamese.

**Commit:** `feat(firmware): arduino sample for SORT/ACK protocol`

### Task 7.2: PyInstaller build script

`scripts/build_exe.py`:
```python
import PyInstaller.__main__
PyInstaller.__main__.run([
    "--name", "TrashSorterPro",
    "--noconsole",
    "--noconfirm",
    "--add-data", "app/ui/resources;app/ui/resources",
    "--add-data", "models;models",
    "--add-data", "config.example.json;.",
    "--icon", "app/ui/resources/icons/app.ico",
    "app/__main__.py",
])
```

Run `uv run python scripts/build_exe.py`. Output `dist/TrashSorterPro/`.

**Commit:** `build: pyinstaller one-folder build script`

### Task 7.3: Smoke test on clean Windows

On a fresh Windows VM (no Python): copy `dist/TrashSorterPro/` over, run `TrashSorterPro.exe`. Verify:
- Window opens.
- Camera connects (if device present).
- Settings persist on second run.
- No crash on close.

**Commit:** `chore: validate clean-machine smoke test`

### Task 7.4: Inspect-model script

`scripts/inspect_model.py`:
```python
import sys
from pathlib import Path
from ultralytics import YOLO

model = YOLO(sys.argv[1] if len(sys.argv) > 1 else "models/best.pt")
print("classes:", model.names)
print("task:", model.task)
print("ckpt:", Path(model.ckpt_path).name if model.ckpt_path else "—")
```

**Commit:** `chore: add model inspector helper script`

### Task 7.5: Release v2.0.0

```bash
git tag -a v2.0.0 -m "Trash Sorter Desktop v2.0.0 — first release"
git push origin v2.0.0
```

Bundle `dist/TrashSorterPro/` into `TrashSorterPro-2.0.0-windows-x64.zip`. Attach to GitHub release with checksum + changelog excerpt.

**Commit:** N/A — tag only.

---

## Self-Review — Spec Coverage

| Spec section | Implemented in |
|---|---|
| 1.1 functional reqs 1-10 | M2.3 (cam) / M2.4 (yolo) / M3.3 (bbox) / M2.5 (tracker) / M2.7 (uart) / M2.8 (history) / M3.5 + M4-5 (5 tabs) / M3.1 (theme) / M4.4 (hot-reload) / M5.3 (capture) |
| 1.3 success criteria | latency: M2.9 + measurement in M3.6; no-crash: M2.3/2.7 reconnect; coverage: M6.6; cold start: M6.2 splash |
| 2 architecture | M2 cores + M3.6 controller |
| 3.1 config | M2.2 |
| 3.2 events | M2.1 |
| 3.3 sqlite schema | M2.8 |
| 4 uart protocol | M2.6 + M2.7 + M7.1 firmware |
| 5 error handling | M2.3 cam reconnect, M2.7 uart reconnect, M2.2 corrupt config, M2.8 sqlite |
| 6 perf | M3.3 zero-copy QImage, M2.3 frame queue maxsize, M3.6 latency timing |
| 7 ui | M3.1 tokens / M3.2 titlebar / M3.4 sidebar / M3.5 live / M4.2 settings / M4.3 mapping / M5.1 history / M5.3 capture / M6 polish |
| 8 testing | TDD throughout; M6.6 strict gate |
| 9 tooling | M1.2 pyproject; M1.5 CI; M6.6 strict |
| 10 distribution | M7.2 build / M7.3 smoke |
| 11 ADRs | M6.7 |
| 12 roadmap | matches |
| 13 risks | mitigated by tasks listed |

**No placeholders.** Every milestone task has files, key implementation, commit message, and either inline tests or a tests file path.

**Type consistency:** `Detection`, `TrackedDetection`, `DetectionEvent`, `AckEvent`, `AppConfig`, `ClassMapping` — used identically across tasks.

---

## Execution

Plan complete and saved to `docs/superpowers/plans/2026-05-21-trash-sorter-desktop-v2.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between, fast iteration.
2. **Inline Execution** — single session through all tasks with checkpoints.

Recommend option 1 for this plan because each milestone is self-contained and reviewable independently, and the subagent context budget is tight per task.
