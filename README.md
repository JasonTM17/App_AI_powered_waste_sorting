# Trash Sorter Pro

Ứng dụng phân loại rác dùng YOLO, camera USB, UART và dashboard web local. Dự án có hai giao diện chạy song song:

- Desktop PySide6 để vận hành trực tiếp trên máy phân loại.
- Web dashboard Next.js gọi FastAPI local agent để xem live, quản lý data, mapping, settings và log.

## Yêu Cầu

- Windows 10/11.
- Python 3.10-3.12 và `uv`.
- Node.js 20 or newer with `npm`.
- GPU NVIDIA nếu muốn train local. Repo đang khóa Torch CUDA `cu128` cho RTX 3060.
- Camera USB ngoài. App không fallback webcam laptop.
- Arduino/ESP32 USB nếu dùng UART; Bluetooth COM và COM thường bị khóa theo quy tắc USB-only.

## Chạy Nhanh

```powershell
cd "D:\PHAN LOAI RAC\trash-sorter-v2"
python -m uv sync --frozen
cd web
npm ci
cd ..
python -m uv run python -m app
```

Chạy agent và web dashboard:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1
```

`start_local.ps1` checks a fresh checkout before launching. When `.venv` or
`web/node_modules` is missing, it runs `python -m uv sync --frozen` or `npm ci`
automatically. It stops with an actionable error when Python, Node.js, npm, or a
required runtime model is unavailable.

Fresh-clone checklist:

```powershell
git clone https://github.com/JasonTM17/App_AI_powered_waste_sorting.git
cd App_AI_powered_waste_sorting
Test-Path models/best.pt
Test-Path models/new-class-specialist.pt
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1
```

Both `Test-Path` commands must print `True`. The repository includes the primary
and specialist runtime models; datasets, local databases, `.env.local`, training
runs, and candidate checkpoints remain intentionally excluded. The first run can
take several minutes while Python CUDA packages and web dependencies are installed.

Trong desktop có nút `Mở Web`; bấm nút này app sẽ tự bật agent + web local nếu chưa chạy, rồi mở màn đăng nhập web dashboard. Sau khi đăng nhập, Admin vào dashboard vận hành, User vào dashboard báo cáo.

Mặc định:

- Agent: `http://localhost:8765`
- Web: `http://localhost:3000`
- Model production: `models/best.pt`
- Dataset training: `dataset_v2/low_conf_queue`
- Export YOLO: `dataset_v2/yolo_trainset`

## Web Login And Roles

The web dashboard now uses username/password login. For production, store accounts
and sessions in PostgreSQL by setting `TRASH_SORTER_AUTH_DATABASE_URL` or
`DATABASE_URL` before starting the local agent. SQLite remains only as the local
fallback when no PostgreSQL URL is configured:

- `admin` role: full dashboard, camera/live, dataset, mapping, settings, logs.
- `user` role: user dashboard only; shows bin fullness, 7/30/90/180-day waste analytics, charts, yesterday summary, and wellness suggestions.

Local dev defaults are enabled by both `scripts/start_local.ps1` and the
desktop `Mở Web` launcher when no production auth/bootstrap env or existing
auth DB is configured. They start the local agent with
`TRASH_SORTER_AUTH_DEV_DEFAULTS=1`:

- Admin: `admin` / `admin123`
- User: `user` / `user123`

These dev accounts are marked `password_default=true`; after login they can only
call `/api/me`, logout, and `/api/auth/change-password` until the password is
changed. For production bootstrap, set `TRASH_SORTER_BOOTSTRAP_ADMIN_USERNAME` and
`TRASH_SORTER_BOOTSTRAP_ADMIN_PASSWORD` before launching the desktop app/web, or
create accounts with:

```powershell
python -m uv run python scripts/manage_auth_accounts.py create owner --role admin --force-change
python -m uv run python scripts/manage_auth_accounts.py set-password owner
python -m uv run python scripts/manage_auth_accounts.py create viewer --role user --force-change
```

Quick account notes:

- `admin` / `admin123` - initial local dev default admin before forced password change.
- `user` / `user123` - initial local dev default user before forced password change.
- `owner` - bootstrap/admin account for production-style setup; set password locally.
- `viewer` - bootstrap/user account for production-style setup; set password locally.
- Member demo usernames: `nguyen-son`, `ngoc-quyen`, `gia-kiet`, `minh-huy`,
  and `hong-thuy`.

Do not commit rotated local passwords, generated auth DBs, `.env*`, or real
PostgreSQL URLs. Keep production credentials in the operator password manager
and set them through environment variables on the target machine.

Seed or refresh the five member accounts locally with:

```powershell
python -m uv run python scripts/seed_member_accounts.py
```

The script generates one-time temporary passwords, prints them to the terminal,
updates display names, and revokes old sessions for accounts it refreshes. Save
the generated values outside the repo, then rotate them with:

```powershell
python -m uv run python scripts/manage_auth_accounts.py set-password <username>
```

Set or repair display names without changing passwords:

```powershell
python -m uv run python scripts/manage_auth_accounts.py set-display-name nguyen-son "Nguyen Son"
```

Auth configuration:

- `TRASH_SORTER_AUTH_DATABASE_URL`: preferred PostgreSQL URL for account/session storage.
- `DATABASE_URL`: supported fallback PostgreSQL URL used by many deploy platforms.
- `TRASH_SORTER_AUTH_DB`: optional auth DB path; defaults to `%APPDATA%/TrashSorter/auth.db`.
- `TRASH_SORTER_SESSION_HOURS`: session lifetime, default `12`.
- `TRASH_SORTER_ALLOWED_ORIGINS`: comma-separated FastAPI CORS origins for production deploys.
- `TRASH_SORTER_ADMIN_TOKEN`, `TRASH_SORTER_USER_TOKEN`, and `TRASH_SORTER_AGENT_TOKEN` remain supported as legacy local/script compatibility tokens.

The desktop launcher preserves production auth settings. It will not inject dev
default accounts when `TRASH_SORTER_AUTH_DATABASE_URL`, `DATABASE_URL`,
`TRASH_SORTER_AUTH_DB`, bootstrap admin env, or an existing default auth DB is
present.

If no auth accounts and no legacy token are configured, direct local API development
stays admin-compatible. The web UI still shows the login screen until a session token
is created.

User data ownership:

- New history rows can be owned by the configured device owner in `config.json`:
  `device.owner_username`, `device.device_id`, `device.device_name`, `device.location`.
- A User session only sees history rows owned by that account. Admin sees all rows.
- Legacy rows with no owner are not exposed to User automatically. Admin can use the
  web Account tab backfill action when the machine should assign old rows to one owner.
- This phase does not identify the person at the bin. For per-person accuracy later,
  add RFID, login-at-bin, or identity hardware before writing owner rows.

Local operations map:

- The local agent stores role-safe operations data in the shared PostgreSQL DB
  when `TRASH_SORTER_OPERATIONS_DATABASE_URL`, `TRASH_SORTER_AUTH_DATABASE_URL`,
  or `DATABASE_URL` is configured. If no URL is configured, it falls back to
  `%APPDATA%/TrashSorter/operations.db`.
- Startup seeds 10 editable Thu Duc candidate stations. Each station creates
  three child bins: `O/bin1`, `R/bin2`, and `I/bin3`. Seed coordinates are
  starter data; `coordinate_verified=false` until Admin verifies them on the map.
- The first two seed stations are assigned to `device.owner_username` or the
  local default user `user`; user sessions only see stations assigned to their
  username. Admin still sees the full map.
- UART bin fullness messages such as `BIN:2:95` update the matching child bin,
  then web alerts derive warning/full states from the persisted DB value.
- Admin APIs manage roles, devices, bin map, alerts, collection schedules, model,
  audio, and reports. User APIs are scoped to map, alerts, schedule, mark-collected,
  device issue reporting, own history, and own account.
- Supabase Realtime push notifications are still a later enhancement; the current
  web UI refreshes/polls the local agent APIs.

Full Stitch User screens:

- Stitch source: `projects/11781034156481807416`, design system
  `assets/4bc3c1426eeb4c778d3a4334c3ece067`.
- Admin keeps the existing operational tabs and now also has `/admin?tab=roles`,
  `/admin?tab=devices`, `/admin?tab=bin-map`, `/admin?tab=alerts`,
  `/admin?tab=model`, `/admin?tab=audio`, and `/admin?tab=reports`.
- User routes are available at `/user/dashboard`, `/user/ecopet`,
  `/user/advice`, `/user/map`, `/user/alerts`, `/user/schedule`,
  `/user/collect`, `/user/report-issue`, `/user/history`, `/user/device`,
  `/user/analytics`, `/user/reports`, `/user/notifications`, `/user/community`,
  `/user/leaderboard`, and `/user/account`.
- User reports use `/api/user/report` and `/api/user/history/export.csv`.
  The User CSV intentionally excludes image paths, raw file paths, logs, tokens,
  password material, and raw history internals.
- Notifications, community cards, leaderboard, and challenges are local MVP
  screens derived from owned `history.db` rows and device status. They are not a
  cloud/social backend in this phase.

DeepSeek AI chatbot/advisor:

- Gắn API key ở backend local agent, không gắn trong frontend và không dùng biến
  `NEXT_PUBLIC_*`. Biến cần đặt là `DEEPSEEK_API_KEY` trong môi trường chạy FastAPI
  agent (`scripts/run_agent.py`, `scripts/start_local.ps1`, hoặc desktop `Mở Web`).
- File env để điền key local: copy `D:\PHAN LOAI RAC\trash-sorter-v2\.env.example`
  thành `D:\PHAN LOAI RAC\trash-sorter-v2\.env.local`, rồi điền:
  `DEEPSEEK_API_KEY=sk-...`. File `.env.local` bị git ignore và được `scripts/start_local.ps1`
  cùng desktop `Mở Web` tự nạp trước khi bật agent.
- Chạy local một lần bằng PowerShell:
  `$env:DEEPSEEK_API_KEY="sk-..."; powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1`
- Nếu mở bằng desktop app, đặt Windows user env trước rồi mở lại app:
  `setx DEEPSEEK_API_KEY "sk-..."`
- Optional: set `DEEPSEEK_BASE_URL`; default is `https://api.deepseek.com`.
- Model is fixed to `deepseek-v4-flash` in this phase. Do not use
  `DEEPSEEK_MODEL` to switch runtime models; keeping one model avoids V4
  thinking-mode/empty-content drift.
- Optional: set `DEEPSEEK_TIMEOUT_SECONDS`; default is `75`.
- This is domain-trained through backend prompt profiles plus local EcoSort
  Knowledge/RAG (`trash_sorter_user`, `trash_sorter_admin`), not hosted
  fine-tuning. Seed knowledge lives in
  `app/agent/knowledge_packs/trash_sorter_base.json`; Admin edits are stored in
  `%APPDATA%/TrashSorter/chat_knowledge.local.json`.
- Admin can open the Account tab and use `Huấn luyện AI` to add/edit snippets,
  enable/disable local knowledge, reload the local file, and run retrieval tests
  before asking DeepSeek.
- The chatbot sends only aggregate counts, chart summaries, scoped history DTOs,
  device status, and sanitized log counts. It does not send camera frames, dataset
  images, file paths, raw logs, passwords, hashes, salts, or session tokens.
- Map questions use a sanitized `operations_map` context. Admin sees all active
  stations/bins/alerts; User sees only stations assigned to that account.
- Advice is general wellness/lifestyle guidance, not medical diagnosis.

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

Mặc định app dùng `Loa phần cứng` khi có OPEN-SMART/GD5800. Nếu Admin chọn
`Loa máy tính`, app phát MP3 từ voice pack đang chọn
`assets/audio/gd5800/Giọng nữ` hoặc `assets/audio/gd5800/Giọng nam` ngay lúc
lệnh UART được chấp nhận và chuẩn bị gửi, không chờ ACK. Ánh xạ hiện tại:

- `O` -> voice pack hữu cơ.
- `R` -> voice pack vô cơ.
- `I` -> voice pack tái chế.
- Cảnh báo nhiều object -> voice pack "chỉ 1 loại rác" hoặc GD5800 track `8`.

## Data Và Train

Audit dataset:

```powershell
python -m uv run python scripts/audit_dataset.py
```

The audit also reports the YOLO `data.yaml` contract. Use strict mode before
model promotion to block class-count, name-order, or catalog drift:

```powershell
python -m uv run python scripts/audit_dataset.py --strict-trainset
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
python -m uv run python scripts/preflight_runtime.py
cd web
npm run build
npm run test:e2e
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
| Tai che | I | `taiche\n` | 3 | D6=160, D7=180 | track 3 |

- Wait/upright position after every dump: D6=90, D7=85.
- Audio output defaults to the OPEN-SMART hardware speaker. Admin can switch
  Settings -> Am thanh / Loa phan loai to `Loa may tinh` and choose `Giong nu`
  or `Giong nam` for bundled MP3 playback. PC speech fires at UART send time,
  not after ACK. In PC-speaker mode the app sends `SORTSILENT:<O|R|I>` so the
  firmware moves the servos without playing the hardware sort track.
- Startup audio: OPEN-SMART track `1`.
- OPEN-SMART Serial MP3 Player A wiring after real probe: Arduino TX `D5` to MP3 RX, Arduino RX `D4` from MP3 TX (`MP3:MODE:REVERSE`, `MP3RX` confirmed). Original D4/D5 primary mode remains available for diagnostics.
- Audio protocol: select TF `7E 03 35 01 EF`, set volume `7E 03 31 <volume> EF`, play track `7E 04 41 00 <track> EF`.
- Proximity sensors are active-low audio-only inputs: Huu co `D10` track `5`, Tai che `D11` track `6`, Vo co `D12` track `7`.
- Sensor events only play tracks `5/6/7` and publish `PROX:*`; they do not move D6/D7 or create a sorting history row.
- This profile does not use HC-SR04 fullness sensors because D6/D7 are servo pins.
- If UART config is blank and exactly one USB/Arduino/CH340 port is found, the app auto-selects and saves it.
- UART ACK timeout defaults to `4500ms`. Firmware holds the dump angle for
  `1800ms`, returns to HOME in 2-degree/10ms steps, settles for `250ms`, then
  detaches the servos. Measured O/R/I ACK times remain below `3500ms`.
- Admin desktop/web can test each bin and see payload, port, ACK/no ACK, and elapsed time.
- Admin web also has raw D6/D7 calibration tests for replaying candidate positions before locking a production angle.
- If UART is off, UI shows `UART OFF, khong gui xuong phan cung`.
- Admin desktop/web has `Actuation Test Mode` for the real camera path: detected class -> group -> bin -> serial payload -> UART sent -> ACK -> history row. Use this before placing real test objects in front of the camera.
- Camera-driven dispatch is guarded by defaults in `dispatch_guard`: at least `3` stable frames, `12s` between any two sort commands, one active dump until ACK/NACK/timeout plus `1s` settle, tray empty for `2s` and `10` frames before re-arm, and a valid enabled ROI. Manual Test Huu co/Vo co/Tai che buttons remain direct hardware tests.
