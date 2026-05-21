# Trash Sorter Desktop v2

Ứng dụng phân loại rác desktop dùng YOLO + UART để điều khiển động cơ phân loại tự động.

## Yêu cầu hệ thống

- Windows 10/11 hoặc Linux x64
- Python 3.10–3.12 (uv tự fetch nếu thiếu)
- Camera USB hoặc IP
- Board điều khiển (Arduino / ESP32) trên cổng COM với firmware tương thích `SORT:<cmd>:<conf>` protocol

## Quick start

```bash
# 1. Cài uv (one-time)
pip install uv

# 2. Sync dependencies
python -m uv sync

# 3. Đặt model YOLO vào models/best.pt
cp /path/to/your/best.pt models/

# 4. Chạy app
python -m uv run python -m app
```

App khởi động với splash screen, sau đó mở cửa sổ chính frameless dark theme.

## Cấu trúc thư mục

```
trash-sorter-v2/
├── app/
│   ├── core/        # camera, inference, tracker, uart, history, pipeline
│   ├── ui/          # widgets, pages, controller
│   └── utils/       # logging, paths, i18n
├── docs/
│   └── adr/         # architecture decision records
├── firmware/        # arduino sample
├── models/          # YOLO best.pt (gitignored)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── ui/
├── pyproject.toml
└── config.example.json
```

Xem `docs/adr/` để hiểu các quyết định kiến trúc.

## Tabs

- **Live**: video real-time với bbox + 6 stat card (FPS, latency, total, etc.).
- **Lịch sử**: filter by ngày/class/ack, bar chart phân bố lớp, area chart theo giờ, table virtualized.
- **Mapping**: chỉnh `class → 1-char UART command + bin index`, có Test button + protocol preview live.
- **Capture**: queue ảnh confidence thấp, export YOLO format để re-train.
- **Cài đặt**: camera/model/UART/app — Test buttons từng section, hot-reload model, atomic save.

## Test

```bash
python -m uv run pytest -q
```

Hiện ~68 test, coverage `app/core` ≥ 65% (gate trong CI).

## Build (Windows)

```bash
python -m uv run python scripts/build_exe.py
```

Output `dist/TrashSorterPro/` (PyInstaller one-folder, không cần Python sẵn ở máy đích).

## UART protocol

App → board (newline-terminated):
- `SORT:<cmd>:<conf>\n` (e.g. `SORT:S:0.92`)
- `PING\n`

Board → app:
- `ACK:<cmd>\n`
- `NACK:<cmd>:<reason>\n`
- `PONG\n`
- `LOG:<text>\n`

Xem ADR-0004 để biết thêm.

## Cấu hình

`%APPDATA%/TrashSorter/config.json` (Windows) hoặc `~/.config/trash-sorter/config.json` (Linux). Mở tab Cài đặt trong app để chỉnh, hoặc edit file rồi restart.

`config.example.json` ở root là template với 6 mapping default (paper/plastic/metal/glass/organic/cardboard).

## License

MIT (xem file LICENSE).

## Contributing

PRs welcome. Trước khi mở PR, chạy:

```bash
python -m uv run ruff format .
python -m uv run ruff check .
python -m uv run pytest
```

CI sẽ enforce coverage gate ≥ 65% trên `app/core`.

## Roadmap

- v2.0 (current): desktop app standalone.
- v2.1: web dashboard online (FastAPI + Next.js), edge agent push HMAC-signed events.
- v2.2: Edge optimizations (TensorRT export, multi-camera).

## Tham khảo

- Dataset gốc: https://universe.roboflow.com/projectverba/yolo-waste-detection
- Ultralytics YOLO: https://docs.ultralytics.com
- PySide6: https://doc.qt.io/qtforpython-6
