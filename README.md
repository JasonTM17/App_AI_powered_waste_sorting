# Trash Sorter Pro

Ứng dụng phân loại rác dùng YOLO, camera USB, UART và dashboard web local. Dự án có hai giao diện chạy song song:

- Desktop PySide6 để vận hành trực tiếp trên máy phân loại.
- Web dashboard Next.js gọi FastAPI local agent để xem live, quản lý data, mapping, settings và log.

## Yêu Cầu

- Windows 10/11.
- Python 3.10-3.12 và `uv`.
- GPU NVIDIA nếu muốn train local. Repo đang khóa Torch CUDA `cu128` cho RTX 3060.
- Camera USB ngoài. App không fallback webcam laptop.
- Arduino/ESP32 USB nếu dùng UART; Bluetooth COM và COM thường bị khóa theo quy tắc USB-only.

## Chạy Nhanh

```powershell
cd "D:\PHAN LOAI RAC\trash-sorter-v2"
python -m uv sync
python -m uv run python -m app
```

Chạy agent và web dashboard:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1
```

Trong desktop có nút `Mở Web`; bấm nút này app sẽ tự bật agent + web local nếu chưa chạy, rồi mở dashboard để annotate/quản lý data.

Mặc định:

- Agent: `http://localhost:8765`
- Web: `http://localhost:3000`
- Model production: `models/best.pt`
- Dataset training: `dataset_v2/low_conf_queue`
- Export YOLO: `dataset_v2/yolo_trainset`

## Web Roles

Web local supports role tokens:

- `TRASH_SORTER_ADMIN_TOKEN`: full dashboard, camera/live, dataset, mapping, settings, logs.
- `TRASH_SORTER_USER_TOKEN`: user dashboard only; shows bin fullness, recent waste composition, and general wellness suggestions.
- `TRASH_SORTER_AGENT_TOKEN`: legacy admin token fallback.

If no token is configured, local development stays admin-compatible. Once any token is configured, the web must provide a valid token. `NEXT_PUBLIC_AGENT_TOKEN` only seeds the first token value; the dashboard can save/change token at runtime.

## Quy Tắc Camera Và UART

- Chỉ dùng camera USB ngoài.
- Khi không có USB camera, preview giữ màn hình đen và `current_source=""`.
- UART chỉ bật khi chọn đúng cổng USB/Arduino thật.
- Nếu không có UART, nhận diện vẫn chạy bình thường bằng no-op sender.
- Checklist gắn mạch: `docs/hardware_integration_checklist.md`.

## Mapping 3 Thùng Và Loa

Model vẫn nhận diện 42 class chi tiết, nhưng app điều khiển máy theo 3 nhóm vận hành:

- `O`, thùng `1`: Hữu cơ.
- `R`, thùng `2`: Vô cơ.
- `I`, thùng `3`: Tái chế.

Khi pipeline emit một object mới, app lưu lịch sử, gửi lệnh UART tương ứng và phát loa theo nhóm rác. Loa có cooldown mặc định `2.5s` để không đọc lặp liên tục khi camera thấy cùng một loại rác.

## Data Và Train

Audit dataset:

```powershell
python -m uv run python scripts/audit_dataset.py
```

Import the three downloaded pen/hardware datasets:

```powershell
python -m uv run python scripts/import_roboflow_dataset.py --zip "$env:USERPROFILE\Downloads\PEN.v3i.yolov8.zip" --source-name roboflow_pen_v3 --label-map pen_hardware_downloads
python -m uv run python scripts/import_roboflow_dataset.py --zip "$env:USERPROFILE\Downloads\Version2.v1i.yolov8.zip" --source-name roboflow_version2 --label-map pen_hardware_downloads
python -m uv run python scripts/import_roboflow_dataset.py --zip "$env:USERPROFILE\Downloads\cardboard-paper.v1i.yolov8.zip" --source-name roboflow_cardboard_paper --label-map pen_hardware_downloads
```

Desktop Data tab and Web Data panel can save the current USB camera frame as a
manual sample. Camera samples are marked as needing annotation; open Web
annotate and adjust the box around the object before using them for training.

Guided Pen capture keeps Actuation Test Mode off and collects 24 quality-gated
frames. Rotate or move the pen before each capture. The session rejects blurry
or duplicate frames, reserves six split-locked holdout frames, and keeps every
sample pending bbox review.

Reviewed manual references are indexed with MobileNetV3-Small embeddings.
Unknown detections are relabeled only when top-5 reference voting has at least
three votes, meets the similarity threshold, and clears the runner-up margin.
Holdout images never enter this reference index.

Export trainset sạch, chỉ lấy item trusted/reviewed:

```powershell
python -m uv run python scripts/export_yolo_trainset.py
```

Smoke train GPU:

```powershell
python -m uv run python scripts/train_yolo.py --device 0 --epochs 1 --imgsz 640 --batch 4 --workers 0 --fraction 0.01 --name trash-sorter-v3-smoke --exist-ok
```

Train candidate thật:

```powershell
python -m uv run python scripts/train_yolo.py --device 0 --epochs 100 --imgsz 640 --batch 16 --workers 0 --patience 20 --name trash-sorter-v3 --exist-ok
```

Fast balanced Pen candidate:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_pen_fast_training.ps1
```

This exports at most 4,500 images with the fixed 45-class contract, preserves
capture-session splits, caps generated data per class, trains 12 frozen epochs
at 512px, then 8 unfrozen epochs at 640px. It never promotes `models/best.pt`.

Evaluate candidate:

```powershell
python -m uv run python scripts/evaluate_yolo.py --model runs\train\trash-sorter-v3\weights\best.pt --split test
```

Không thay `models/best.pt` bằng model mới cho tới khi candidate tốt hơn model cũ và đã test camera thật.

## Data Hiện Tại

- Roboflow trusted: `13,104` ảnh.
- Tổng dataset hiện tại: `14,974` ảnh / `21,204` box.
- Class: `42`.
- Data cần duyệt: `776` item.
- Manual import hiện tại: `50` ảnh.

Các class hiếm nên bổ sung thêm data: `Aluminum caps`, `Metal shavings`, `Iron utensils`, `Wood`, `Cellulose`, `Furniture`, `Combined plastic`, `Foil`, `Ceramic`, `Plastic caps`, `Electronics`, `Scrap metal`, `Stretch film`, `Paper shavings`, `Disposable tableware`.

## Test

```powershell
python -m uv run ruff check app scripts tests
python -m uv run mypy app/core
python -m uv run pytest -q
cd web
npm run build
npm audit --audit-level=moderate
```

## Build Desktop EXE

```powershell
python -m uv run python scripts/build_exe.py
```

Output nằm ở `dist/TrashSorterPro/`.

## UART Protocol

App gửi:

- `SORT:<cmd>:<conf>`
- `PING`

Lệnh vận hành 3 thùng:

- `O`: thùng 1, Hữu cơ.
- `R`: thùng 2, Vô cơ.
- `I`: thùng 3, Tái chế.

Mặc định app dùng giao thức block kéo thả giống mạch demo:

- `O` gửi `huuco`
- `R` gửi `voco`
- `I` gửi `taiche`

Mapping nhận diện 42 class vào 3 nhóm:

- Hữu cơ (`O/huuco/bin1`): `Liquid`, `Organic`, `Wood`.
- Tái chế (`I/taiche/bin3`): `Aluminum can`, `Aluminum caps`, `Cardboard`,
  `Cellulose`, `Combined plastic`, `Foil`, `Glass bottle`, `Iron utensils`,
  `Metal shavings`, `Milk bottle`, `Paper`, `Paper bag`, `Paper cups`,
  `Paper shavings`, `Papier mache`, `Plastic bag`, `Plastic bottle`,
  `Plastic can`, `Plastic canister`, `Plastic caps`, `Plastic cup`,
  `Plastic shaker`, `Plastic shavings`, `Postal packaging`,
  `Printing industry`, `Scrap metal`, `Stretch film`, `Tetra pack`, `Tin`,
  `Zip plastic bag`.
- Vô cơ (`R/voco/bin2`): các class còn lại như `Aerosols`, `Ceramic`,
  `Container for household chemicals`, `Disposable tableware`, `Electronics`,
  `Furniture`, `Plastic toys`, `Textile`, `Unknown plastic`, `Pen`, `Pencil`,
  `Marker`.

Small writing tools are routed as inorganic:
`Pen/Pencil/Marker/Battery/Toothbrush -> R/voco/bin2`. They still require
reviewed training data before the YOLO model can detect them.

While the production model is still missing a class, the desktop pipeline does
not stay silent: low-confidence or newly visible objects are rendered as
`Unknown object` and routed to the safe inorganic path `R/voco/bin2`. This
creates a Live box and History row only after the camera dispatch guard allows
it. Camera-driven UART dispatch requires Actuation Test Mode, connected UART, a
valid enabled ROI, the object inside that ROI, stable frames, no active dump, an
empty-tray re-arm, and the global cooldown. If any guard blocks dispatch, Live
still renders the box and shows a status such as `ROI OFF`, `outside ROI`,
`waiting stable`, `waiting empty tray`, `sort busy`, or `cooldown`.

Nếu nạp firmware Arduino trong repo, có thể đổi UART protocol sang `Firmware: SORT:O/R/I`.

Board trả:

- `ACK:<cmd>`
- `NACK:<cmd>:<reason>`
- `PONG`
- `PROFILE:LEGACY_2_SERVO_OPENSMART`
- `MP3TX:<hex>` / `MP3RX:<hex>` for OPEN-SMART Serial MP3 Player A diagnostics.
- `PROX:<cmd>` for active-low audio-only proximity sensors in the selected block profile.
- `BIN:<bin_index>:<percent>` only when using an HC-SR04 firmware profile, for example `BIN:2:75`.
- `LOG:<text>`

## Cấu Trúc Chính

```text
trash-sorter-v2/
├── app/                 # core, desktop UI, agent API
├── web/                 # Next.js dashboard
├── scripts/             # audit, import, export, train, evaluate, build
├── dataset_v2/          # queue + yolo_trainset
├── models/              # best.pt production
├── tests/               # unit/integration/ui tests
├── pyproject.toml
└── config.example.json
```

## Selected Hardware Profile

The current real hardware profile follows the user-provided block diagram and red audio board photo: `LEGACY_2_SERVO_OPENSMART`.

| Group | Cmd | Serial text | Bin | Servo angles | Audio |
|---|---|---|---:|---|---:|
| Huu co | O | `huuco\n` | 1 | D6=90, D7=180 | track 2 |
| Vo co | R | `voco\n` | 2 | D6=90, D7=0 | track 4 |
| Tai che | I | `taiche\n` | 3 | D6=145, D7=180 | track 3 |

- Wait/upright position after every dump: D6=90, D7=85.
- PC speaker is off by default. Valid sort audio is the OPEN-SMART hardware
  speaker; set `TRASH_SORTER_ENABLE_PC_SPEAKER=1` only for debug speech.
- Startup audio: OPEN-SMART track `1`.
- OPEN-SMART Serial MP3 Player A wiring after real probe: Arduino TX `D5` to MP3 RX, Arduino RX `D4` from MP3 TX (`MP3:MODE:REVERSE`, `MP3RX` confirmed). Original D4/D5 primary mode remains available for diagnostics.
- Audio protocol: select TF `7E 03 35 01 EF`, set volume `7E 03 31 <volume> EF`, play track `7E 04 41 00 <track> EF`.
- Proximity sensors are active-low audio-only inputs: Huu co `D10` track `5`, Tai che `D11` track `6`, Vo co `D12` track `7`.
- Sensor events only play tracks `5/6/7` and publish `PROX:*`; they do not move D6/D7 or create a sorting history row.
- This profile does not use HC-SR04 fullness sensors because D6/D7 are servo pins.
- If UART config is blank and exactly one USB/Arduino/CH340 port is found, the app auto-selects and saves it.
- UART ACK timeout defaults to `4500ms` because firmware returns `ACK:<cmd>` after the 2000ms servo hold and return-to-wait movement.
- Admin desktop/web can test each bin and see payload, port, ACK/no ACK, and elapsed time.
- Admin web also has raw D6/D7 calibration tests for replaying candidate positions before locking a production angle.
- If UART is off, UI shows `UART OFF, khong gui xuong phan cung`.
- Admin desktop/web has `Actuation Test Mode` for the real camera path: detected class -> group -> bin -> serial payload -> UART sent -> ACK -> history row. Use this before placing real test objects in front of the camera.
- Camera-driven dispatch is guarded by defaults in `dispatch_guard`: at least `3` stable frames, `12s` between any two sort commands, one active dump until ACK/NACK/timeout plus `1s` settle, tray empty for `2s` and `10` frames before re-arm, and a valid enabled ROI. Manual Test Huu co/Vo co/Tai che buttons remain direct hardware tests.
