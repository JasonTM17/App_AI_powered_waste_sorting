# Trash Sorter Pro

<p align="center">
  <img src="docs/assets/brand/trash-sorter-pro-logo.png" alt="Trash Sorter Pro logo" width="140" />
</p>

> Hệ thống phân loại rác thông minh dùng YOLO, camera USB, điều khiển UART/Arduino,
> desktop app PySide6 và web dashboard Next.js cho Admin/User.

[![Production](https://img.shields.io/badge/Production-trash--sorter--v2.vercel.app-10B981?style=for-the-badge)](https://trash-sorter-v2.vercel.app)
[![Desktop](https://img.shields.io/badge/Desktop-PySide6_+_YOLO-0F172A?style=for-the-badge)](docs/project-showcase.md#desktop-app)
[![Web](https://img.shields.io/badge/Web-Next.js_+_Vercel-2563EB?style=for-the-badge)](docs/project-showcase.md#web-dashboard)
[![Hardware](https://img.shields.io/badge/Hardware-USB_Camera_+_UART-F59E0B?style=for-the-badge)](#quy-tắc-camera-và-uart)
[![Docker Hub](https://img.shields.io/badge/Docker_Hub-nguyenson1710-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://hub.docker.com/u/nguyenson1710)

## Demo production login

Production web: [https://trash-sorter-v2.vercel.app](https://trash-sorter-v2.vercel.app)

| Field | Value |
| --- | --- |
| Role | `user` |
| Username | `demo-user` |
| Password | `TrashSorterDemo#2026!` |

This is a low-privilege public demo account with seeded sample data. It cannot
manage Admin users, devices, hardware mappings, or system-wide settings. Rotate
this password if the account is abused. Real Admin credentials must stay private
and must not be committed to this repository.

## Container/package note

Docker Hub is the complete artifact registry for this project:

- `nguyenson1710/trash-sorter-web`
- `nguyenson1710/trash-sorter-agent`
- `nguyenson1710/trash-sorter-models`
- `nguyenson1710/trash-sorter-desktop-exe`
- `nguyenson1710/trash-sorter-dataset-archive`

GitHub Packages mirrors the same five project packages. The dataset package
includes the index tag plus `part01` to `part10` payload tags; Docker Hub
remains the primary source registry.

## Tổng quan kỹ thuật

Trash Sorter Pro là một hệ sinh thái AI phân loại rác end-to-end, thiết kế theo hướng
local-first để vận hành ổn định với camera USB và phần cứng thật:

- Nhận diện rác bằng YOLO, specialist routes, manual reference và visual correction.
- Gom nhiều nhãn chi tiết về 3 nhóm vận hành: **Hữu cơ**, **Vô cơ**, **Tái chế**.
- Điều khiển máy thật qua desktop app PySide6: camera USB, ROI, UART, loa, lịch sử, mapping, data review và huấn luyện thủ công.
- Theo dõi qua web dashboard Next.js/FastAPI: Admin/User, bản đồ thùng, cảnh báo, lịch thu gom, báo cáo, Eco Score và EcoPet AI.
- Phân quyền rõ ràng: User chỉ xem dữ liệu của chính mình; Admin quản lý toàn hệ thống, camera, phần cứng, dữ liệu và training.
- Production web đang chạy tại: [trash-sorter-v2.vercel.app](https://trash-sorter-v2.vercel.app).

Điểm quan trọng nhất: app **không đổ ngay theo nhãn YOLO thô**. Mỗi frame đi qua
các lớp sửa nhãn, kiểm tra ROI, chống nhiều vật, chờ khay trống, chống spam lệnh và
chỉ gửi UART khi guard cho phép.

## Mục lục đọc nhanh

- [Kiến trúc vận hành](#kiến-trúc-vận-hành)
- [Luồng AI và quyết định đổ](#luồng-ai-và-quyết-định-đổ)
- [Tài liệu chi tiết](#tài-liệu-chi-tiết)
- [Yêu cầu môi trường](#yêu-cầu-môi-trường)
- [Chạy nhanh](#chạy-nhanh)
- [Quy Tắc Camera Và UART](#quy-tắc-camera-và-uart)
- [Mapping 3 Thùng Và Loa](#mapping-3-thùng-và-loa)
- [Data Và Train](#data-và-train)
- [Kiểm thử](#kiểm-thử)
- [Đóng gói Desktop EXE](#đóng-gói-desktop-exe)

## Kiến trúc vận hành

```mermaid
flowchart TD
    subgraph Desktop["Máy phân loại local"]
        App["Desktop PySide6"]
        Camera["USB Camera"]
        Pipeline["Core AI Pipeline"]
        Config["%APPDATA%/TrashSorter/config.json"]
        History["history.db"]
        UART["UART Worker"]
        Speaker["Loa laptop hoặc loa phần cứng"]
        Arduino["Arduino / ESP32"]
    end

    subgraph Web["Giao diện web"]
        Agent["FastAPI Local Agent :8765"]
        Next["Next.js Dashboard :3000"]
        Cloud["Vercel / Hardware Bridge"]
    end

    Camera --> Pipeline
    Config --> App
    App --> Pipeline
    Pipeline --> History
    Pipeline --> UART
    Pipeline --> Speaker
    UART --> Arduino
    Agent --> Pipeline
    Agent --> History
    Next --> Agent
    Cloud --> Agent
```

Các thư mục quan trọng:

| Đường dẫn | Vai trò |
| --- | --- |
| `app/core/` | Pipeline AI, config, inference, guard, UART, speaker, dataset logic. |
| `app/ui/` | Desktop UI PySide6, trang Live/Training/Mapping/Settings. |
| `app/agent/` | FastAPI local agent cho web dashboard và hardware bridge. |
| `web/` | Next.js dashboard cho Admin/User. |
| `models/` | Model runtime đã huấn luyện. |
| `dataset_v2/` | Queue mẫu camera, review, export trainset YOLO. |
| `scripts/` | Audit, import, export, train, evaluate, build EXE. |
| `docs/` | Tài liệu kỹ thuật, showcase, checklist phần cứng, release notes. |

## Luồng AI và quyết định đổ

```mermaid
flowchart TD
    A["Frame từ USB camera"] --> B["YOLO primary + specialist"]
    B --> C["Ngưỡng class riêng"]
    C --> D["Khử bbox chồng / gộp cùng vật"]
    D --> E["Unknown fallback nếu YOLO yếu"]
    E --> F["Manual reference: so mẫu đã duyệt"]
    F --> G["Visual correction: sửa lỗi camera mờ"]
    G --> H["Tracker ổn định theo thời gian"]
    H --> I{"Auto/Test sorting bật?"}
    I -- "Không" --> J["Chỉ hiển thị Live + History preview"]
    I -- "Có" --> K{"Guard đạt?"}
    K -- "Không" --> L["Hiển thị lý do: TEST OFF, UART OFF, ROI, nhiều vật, chờ khay trống..."]
    K -- "Có" --> M["Map class -> O/R/I -> bin"]
    M --> N["Phát loa theo mode đã chọn"]
    M --> O["Gửi UART xuống Arduino"]
    O --> P["ACK/NACK/timeout"]
    P --> Q["Lưu history và chờ re-arm khay trống"]
```

Những sửa lỗi camera thật đang được hỗ trợ:

- Bì ni lông mờ/nhăn có thể bị YOLO gọi nhầm `Paper`; manual reference cho phép sửa `Paper -> Plastic bag`.
- Quả trứng/vỏ trứng có thể rơi vào `Unknown object` hoặc `Pen`; visual correction sửa về `Eggshell` để route Hữu cơ.
- Vật nguy hại như pin cần cảnh báo/xác nhận rõ, không đoán bừa để đổ.
- Khi có nhiều vật hoặc nhiều class trong khay, app cảnh báo “chỉ bỏ 1 loại rác” và không gửi UART.

## Ảnh minh hoạ Desktop app

| Live Detection | Mapping 80 lớp -> 3 thùng |
| --- | --- |
| ![Desktop Live Detection](docs/assets/screenshots/desktop-live-detection.png) | ![Desktop Mapping](docs/assets/screenshots/desktop-mapping.png) |

| Huấn luyện thủ công | Cài đặt camera/ROI/UART |
| --- | --- |
| ![Desktop Training](docs/assets/screenshots/desktop-training.png) | ![Desktop Settings](docs/assets/screenshots/desktop-settings.png) |

## Ảnh nguyên mẫu phần cứng thực tế

Các ảnh dưới đây được chụp trực tiếp từ mô hình đồ án đang vận hành. Chúng giúp
người đọc hình dung vị trí camera, khay nhận diện, cụm servo, mạch điều khiển và
các thùng rác thật trước khi xem video demo.

| Toàn cảnh nguyên mẫu | Thùng Hữu cơ | Thùng Vô cơ và mạch điều khiển |
| --- | --- | --- |
| [![Toàn cảnh mô hình Trash Sorter Pro](docs/assets/demo/photos/trash-sorter-prototype-overview.jpg)](docs/assets/demo/photos/trash-sorter-prototype-overview.jpg) | [![Thùng Hữu cơ của mô hình](docs/assets/demo/photos/organic-bin-prototype.jpg)](docs/assets/demo/photos/organic-bin-prototype.jpg) | [![Thùng Vô cơ và mạch điều khiển](docs/assets/demo/photos/inorganic-bin-controller.jpg)](docs/assets/demo/photos/inorganic-bin-controller.jpg) |

Trong ảnh toàn cảnh, camera USB được đặt phía trên khay nhận diện; cụm servo ở
trục giữa điều hướng vật sang nhóm thùng tương ứng. Hai ảnh cận cảnh cho thấy vị
trí cảm biến theo dõi thùng và board điều khiển UART trên nguyên mẫu thật.

## Video demo sản phẩm

Nhấn vào từng ảnh để mở video MP4 tương ứng:

| Tổng thể sản phẩm | Toàn cảnh mô hình/camera |
| --- | --- |
| [![Video tổng thể Trash Sorter Pro](docs/assets/demo/thumbnails/product-demo-overview.jpg)](docs/assets/demo/product-demo-overview.mp4) | [![Video toàn cảnh mô hình và camera](docs/assets/demo/thumbnails/hardware-front-view.jpg)](docs/assets/demo/hardware-front-view.mp4) |

| Cận cảnh thùng Hữu cơ | Cận cảnh thùng Vô cơ |
| --- | --- |
| [![Video cận cảnh thùng Hữu cơ](docs/assets/demo/thumbnails/organic-bin-demo.jpg)](docs/assets/demo/organic-bin-demo.mp4) | [![Video cận cảnh thùng Vô cơ và mạch điều khiển](docs/assets/demo/thumbnails/inorganic-bin-demo.jpg)](docs/assets/demo/inorganic-bin-demo.mp4) |

Video được quay trực tiếp trên nguyên mẫu phần cứng thật; không phải video mô phỏng.

## Ảnh minh hoạ Web dashboard

| User Dashboard | EcoPet AI |
| --- | --- |
| ![Web User Dashboard](docs/assets/screenshots/web-user-dashboard.png) | ![EcoPet AI trên web](docs/assets/screenshots/web-ecopet-chat.png) |

| Bản đồ thùng | Phân tích |
| --- | --- |
| ![Web Bin Map](docs/assets/screenshots/web-bin-map.png) | ![Web Analytics](docs/assets/screenshots/web-analytics.png) |

| Cảnh báo |
| --- |
| ![Web Alerts](docs/assets/screenshots/web-alerts.png) |

## Tài liệu chi tiết

- [Tài liệu kỹ thuật tiếng Việt: kiến trúc, pipeline AI, UART, loa, training và sơ đồ graph](docs/technical-architecture-vi.md)
- [Project showcase, kiến trúc và GitHub About](docs/project-showcase.md)
- [Hướng dẫn chạy web app](docs/huong-dan-chay-web-app.md)
- [Supabase/cloud readiness](docs/supabase-full-cloud-readiness.md)
- [Docker production stack: web, agent, Supabase bridge, CPU/GPU, push, rollback](docs/docker-production-stack.md)
- [Desktop EXE, Docker Hub, GitHub Packages and keepalive release plan](docs/desktop-dockerhub-keepalive-release-plan.md)
- [Checklist tích hợp phần cứng](docs/hardware_integration_checklist.md)
- [Operations map local-first](docs/operations-map-local-first.md)
- [Release v2.1.0: cloud map and hardware bridge](docs/releases/v2.1.0.md)
- [Release v2.1.1: Admin and User realtime](docs/releases/v2.1.1.md)
- [Release v2.2.0: User experience and Admin operations](docs/releases/v2.2.0.md)

Lộ trình đọc khuyến nghị khi mới vào repo:

1. Đọc README này để hiểu cách chạy, phần cứng, mapping và các lệnh chính.
2. Đọc [docs/technical-architecture-vi.md](docs/technical-architecture-vi.md) để hiểu pipeline kỹ thuật, graph và checklist debug.
3. Đọc [docs/hardware_integration_checklist.md](docs/hardware_integration_checklist.md) trước khi đấu UART/servo/loa.
4. Đọc [docs/huong-dan-chay-web-app.md](docs/huong-dan-chay-web-app.md) nếu cần chạy web dashboard hoặc hardware bridge.

Mở Desktop App bằng `Trash Sorter Pro.lnk` ngay thư mục gốc, hoặc chạy trực tiếp
`dist/TrashSorterPro/TrashSorterPro.exe`.

Dọn cache, log, ảnh kiểm thử và file build tạm mà không đụng dataset/model/config:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/clean_workspace.ps1
powershell -ExecutionPolicy Bypass -File scripts/clean_workspace.ps1 -Apply
```

Dữ liệu tải từ Kaggle được giữ local tại `.local/kagglehub-cache` và không commit lên Git.
Đây là ảnh nguồn để huấn luyện/đánh giá, không phải thành phần app cần khi nhận diện.
Runtime dùng các model đã huấn luyện trong `models/`. Có thể đổi vị trí cache bằng
`TRASH_SORTER_KAGGLE_CACHE` hoặc tham số `--cache-root` của script Kaggle.

Ứng dụng phân loại rác dùng YOLO, camera USB, UART và dashboard web local. Dự án có hai giao diện chạy song song:

- Desktop PySide6 để vận hành trực tiếp trên máy phân loại.
- Web dashboard Next.js gọi FastAPI local agent để xem live, quản lý data, mapping, settings và log.

## Yêu cầu môi trường

- Windows 10/11.
- Python 3.10-3.12 và `uv`.
- Node.js 20 trở lên và `npm`.
- GPU NVIDIA nếu muốn train local. Repo đang khóa Torch CUDA `cu128` cho RTX 3060.
- Camera USB ngoài. App không fallback webcam laptop.
- Arduino/ESP32 USB nếu dùng UART; Bluetooth COM và COM thường bị khóa theo quy tắc USB-only.

## Chạy nhanh

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

`start_local.ps1` kiểm tra checkout mới trước khi chạy. Nếu thiếu `.venv` hoặc
`web/node_modules`, script tự chạy `python -m uv sync --frozen` hoặc `npm ci`.
Nếu thiếu Python, Node.js, npm hoặc model runtime bắt buộc, script dừng với lỗi
có hướng dẫn xử lý.

Checklist sau khi clone mới:

```powershell
git clone https://github.com/JasonTM17/App_AI_powered_waste_sorting.git
cd App_AI_powered_waste_sorting
Test-Path models/best.pt
Test-Path models/new-class-specialist.pt
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1
```

Hai lệnh `Test-Path` phải in ra `True`. Repo có kèm primary model và specialist
runtime model; dataset local, database local, `.env.local`, training runs và
candidate checkpoint được loại khỏi Git có chủ đích. Lần chạy đầu có thể mất vài
phút vì cần cài Python CUDA packages và dependency web.

Trong desktop có nút `Mở Web`; bấm nút này app sẽ mở web production tại `https://trash-sorter-v2.vercel.app/admin?tab=live`. Nếu cần mở dashboard local cho phần cứng/camera, đặt `TRASH_SORTER_DESKTOP_WEB_LOCAL=1` trước khi mở desktop app; khi đó app sẽ tự bật agent + web local nếu chưa chạy.

Mặc định:

- Agent: `http://localhost:8765`
- Web: `http://localhost:3000`
- Model production: `models/best.pt`
- Dataset training: `dataset_v2/low_conf_queue`
- Export YOLO: `dataset_v2/yolo_trainset`

Nhóm chai/lọ dùng ngưỡng class riêng trong `model.class_thresholds` để giữ lại
dự đoán Tái chế có confidence thấp trên camera thật. Pipeline khử các bbox chồng
lấn của cùng một vật trước tracker. Classifier 3 thùng xử lý `Unknown` và có thể
xác nhận `Organic` khi YOLO đồng thời thấy `Paper/Paper bag` và `Organic` với
điểm gần nhau; nhãn kỹ thuật `Kaggle 3-bin` không hiển thị trên Live UI.

## Đăng nhập web và phân quyền

Web dashboard dùng đăng nhập bằng username/password. Khi chạy production, nên lưu
tài khoản và session trong PostgreSQL bằng cách đặt `TRASH_SORTER_AUTH_DATABASE_URL`
hoặc `DATABASE_URL` trước khi bật local agent. SQLite chỉ là fallback local khi
không có PostgreSQL URL.

| Role | Quyền chính |
| --- | --- |
| `admin` | Toàn quyền dashboard, camera/live, dataset, mapping, settings, logs, model, audio, hardware test và training. |
| `user` | Chỉ xem dashboard người dùng: mức đầy thùng, thống kê 7/30/90/180 ngày, biểu đồ, tổng kết hôm qua và gợi ý EcoPet. |

Tài khoản dev mặc định được bật bởi `scripts/start_local.ps1` và nút desktop
`Mở Web` khi chưa có auth DB, chưa có biến production auth/bootstrap và chưa có
database tài khoản sẵn. Khi đó agent chạy với `TRASH_SORTER_AUTH_DEV_DEFAULTS=1`:

- Admin: `admin` / `admin123`
- User: `user` / `user123`

Các tài khoản dev này được đánh dấu `password_default=true`. Sau khi đăng nhập,
tài khoản chỉ được gọi `/api/me`, logout và `/api/auth/change-password` cho tới
khi đổi mật khẩu. Với production bootstrap, đặt
`TRASH_SORTER_BOOTSTRAP_ADMIN_USERNAME` và
`TRASH_SORTER_BOOTSTRAP_ADMIN_PASSWORD` trước khi bật desktop/web, hoặc tạo tài
khoản bằng lệnh:

```powershell
python -m uv run python scripts/manage_auth_accounts.py create owner --role admin --force-change
python -m uv run python scripts/manage_auth_accounts.py set-password owner
python -m uv run python scripts/manage_auth_accounts.py create viewer --role user --force-change
```

Ghi chú tài khoản:

- `admin` / `admin123`: admin dev mặc định, bắt buộc đổi mật khẩu sau đăng nhập.
- `user` / `user123`: user dev mặc định, bắt buộc đổi mật khẩu sau đăng nhập.
- `owner`: tài khoản admin bootstrap cho cấu hình giống production.
- `viewer`: tài khoản user bootstrap cho cấu hình giống production.
- Tài khoản demo thành viên: `nguyen-son`, `ngoc-quyen`, `gia-kiet`, `minh-huy`, `hong-thuy`.

Không commit mật khẩu local đã đổi, auth DB sinh ra, `.env*`, hoặc PostgreSQL URL thật.
Credential production phải nằm trong password manager của người vận hành và được
truyền vào máy đích qua biến môi trường.

Seed hoặc refresh 5 tài khoản thành viên local:

```powershell
python -m uv run python scripts/seed_member_accounts.py
```

Script sẽ sinh mật khẩu tạm một lần, in ra terminal, cập nhật display name và
thu hồi session cũ của các tài khoản được refresh. Lưu giá trị sinh ra ở ngoài
repo, sau đó đổi mật khẩu:

```powershell
python -m uv run python scripts/manage_auth_accounts.py set-password <username>
```

Đặt hoặc sửa display name mà không đổi mật khẩu:

```powershell
python -m uv run python scripts/manage_auth_accounts.py set-display-name nguyen-son "Nguyen Son"
```

Cấu hình auth:

- `TRASH_SORTER_AUTH_DATABASE_URL`: PostgreSQL URL ưu tiên để lưu account/session.
- `DATABASE_URL`: PostgreSQL URL fallback, tương thích nhiều nền tảng deploy.
- `TRASH_SORTER_AUTH_DB`: đường dẫn auth DB tùy chọn; mặc định `%APPDATA%/TrashSorter/auth.db`.
- `TRASH_SORTER_SESSION_HOURS`: thời hạn session, mặc định `12`.
- `TRASH_SORTER_ALLOWED_ORIGINS`: danh sách FastAPI CORS origins, phân tách bằng dấu phẩy.
- `TRASH_SORTER_HARDWARE_BRIDGE_SECRET`: secret server-only cho Admin API khi expose agent qua public tunnel.
- `TRASH_SORTER_HARDWARE_BRIDGE_URL`: HTTPS tunnel URL dùng riêng cho Vercel proxy camera/training của Admin.
- `TRASH_SORTER_ADMIN_TOKEN`, `TRASH_SORTER_USER_TOKEN`, `TRASH_SORTER_AGENT_TOKEN`: token legacy vẫn được hỗ trợ cho script/local compatibility.

Desktop launcher giữ nguyên cấu hình auth production. Nó không tự chèn tài khoản
dev khi đã có `TRASH_SORTER_AUTH_DATABASE_URL`, `DATABASE_URL`,
`TRASH_SORTER_AUTH_DB`, env bootstrap admin hoặc auth DB mặc định hiện hữu.

Nếu chưa cấu hình tài khoản auth và cũng không có legacy token, API local trực tiếp
vẫn tương thích luồng admin dev. Web UI vẫn hiện màn hình đăng nhập cho tới khi có
session token.

Quyền sở hữu dữ liệu User:

- History row mới có thể gắn với chủ thiết bị trong `config.json`:
  `device.owner_username`, `device.device_id`, `device.device_name`, `device.location`.
- User chỉ thấy history row thuộc tài khoản của mình. Admin thấy toàn bộ.
- Row cũ không có owner không tự động lộ cho User. Admin có thể dùng action backfill
  ở tab Account trên web khi muốn gán dữ liệu cũ cho một chủ máy.
- Giai đoạn này chưa nhận diện người đứng trước thùng. Nếu cần độ chính xác theo
  từng người, phải bổ sung RFID, login-at-bin hoặc phần cứng nhận diện danh tính.

Bản đồ vận hành local:

- Local agent lưu dữ liệu vận hành role-safe vào PostgreSQL chung khi có
  `TRASH_SORTER_OPERATIONS_DATABASE_URL`, `TRASH_SORTER_AUTH_DATABASE_URL` hoặc
  `DATABASE_URL`. Nếu không có URL, fallback về `%APPDATA%/TrashSorter/operations.db`.
- Khi startup, hệ thống seed 10 trạm ứng viên khu vực Thủ Đức có thể chỉnh sửa.
  Mỗi trạm tạo 3 thùng con: `O/bin1`, `R/bin2`, `I/bin3`. Tọa độ seed là dữ liệu
  khởi tạo; `coordinate_verified=false` cho tới khi Admin xác nhận trên bản đồ.
- Hai trạm seed đầu được gán cho `device.owner_username` hoặc user local mặc định
  `user`; User chỉ thấy trạm được gán cho username của mình. Admin vẫn thấy toàn bộ bản đồ.
- UART fullness message như `BIN:2:95` cập nhật đúng thùng con, sau đó web alerts
  suy ra trạng thái warning/full từ DB.
- Admin API quản lý role, thiết bị, bản đồ thùng, cảnh báo, lịch thu gom, model,
  audio và reports. User API bị scope vào bản đồ, cảnh báo, lịch, đánh dấu đã thu gom,
  báo lỗi thiết bị, history của chính mình và account của chính mình.
- Supabase bin/alert triggers ghi `realtime_events` theo scope. Admin/User dashboard
  map đọc cursor đã xác thực mỗi 1.2 giây và refresh sau sự kiện mức đầy; poll 6 giây
  vẫn là fallback khi realtime gián đoạn.

Hardware bridge public cho Admin:

- Hướng dẫn chạy tunnel ổn định sau reboot Windows:
  [docs/huong-dan-chay-web-app.md](docs/huong-dan-chay-web-app.md#11-chạy-tunnel-ổn-định-sau-khi-bật-máy-windows).
- Chỉ dùng bridge này cho Admin camera/live/training từ thiết bị khác. Role User vẫn
  bị chặn khỏi camera, dataset capture, training, settings, model, logs và hardware test APIs.
- Cài Cloudflare Tunnel (`cloudflared`) trên máy phần cứng, sau đó chạy:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_public_hardware_bridge.ps1
```

- Script đảm bảo `TRASH_SORTER_HARDWARE_BRIDGE_SECRET` tồn tại trong `.env.local`,
  bật local agent nếu cần, rồi mở tunnel tới `http://127.0.0.1:8765`.
- Copy URL `https://*.trycloudflare.com` sinh ra trong
  `logs/public-hardware-bridge.err.log` lên Vercel production thành
  `TRASH_SORTER_HARDWARE_BRIDGE_URL`, đồng thời đặt cùng secret ở Vercel bằng
  `TRASH_SORTER_HARDWARE_BRIDGE_SECRET`.
- Chỉ đặt `NEXT_PUBLIC_USE_CLOUD_HARDWARE_BRIDGE=1` cho deployment Vercel dùng bridge.
  Build local/operator giữ biến này trống hoặc `0` để Admin camera/live gọi cùng
  local agent với desktop app.
- Khi bridge secret bật, dùng Vercel Admin UI cho public camera/live/training.
  Browser local dev gọi trực tiếp protected Admin API sẽ bị từ chối nếu không tắt
  secret và restart agent.
- Vercel chỉ proxy allowlist: status, camera start/stop/stream-token, model class
  catalog, camera sample capture, capture-session, learn-now status/refresh/unknown
  capture và micro-train start. Settings writes, logs, model/audio config,
  servo/UART tests và generic proxy không được expose qua public bridge.
- Admin Live/Camera đọc cùng detection snapshot của local `Pipeline` như desktop app.
  Production poll protected hardware snapshot mỗi giây khi màn camera mở; camera frame
  và AI result vẫn chỉ dành cho Admin.
- Khi có Supabase/Auth database URL, public bridge cũng bật hardware-state synchronizer.
  `BIN:<index>:<percent>` đi vào cloud operations theo chu kỳ 2 giây.

Màn hình User từ Stitch:

- Stitch source: `projects/11781034156481807416`, design system
  `assets/4bc3c1426eeb4c778d3a4334c3ece067`.
- Admin giữ các tab vận hành hiện có và có thêm `/admin?tab=roles`,
  `/admin?tab=devices`, `/admin?tab=bin-map`, `/admin?tab=alerts`,
  `/admin?tab=model`, `/admin?tab=audio`, `/admin?tab=reports`.
- User routes hiện có: `/user/dashboard`, `/user/ecopet`,
  `/user/advice`, `/user/map`, `/user/alerts`, `/user/schedule`,
  `/user/collect`, `/user/report-issue`, `/user/history`, `/user/device`,
  `/user/analytics`, `/user/reports`, `/user/notifications`, `/user/community`,
  `/user/leaderboard`, `/user/account`.
- User reports dùng `/api/user/report` và `/api/user/history/export.csv`.
  CSV của User cố tình loại image path, raw file path, logs, tokens, password material
  và raw history internals.
- Notifications, community cards, leaderboard và challenges là màn local MVP suy ra
  từ `history.db` theo owner và trạng thái thiết bị. Giai đoạn này chưa phải cloud/social backend.

DeepSeek AI chatbot/advisor:

- Gắn API key ở backend, không gắn trong frontend và không dùng biến `NEXT_PUBLIC_*`.
  Local FastAPI và Next.js server trên Vercel đều đọc biến server-side `DEEPSEEK_API_KEY`.
- File env để điền key local: copy `D:\PHAN LOAI RAC\trash-sorter-v2\.env.example`
  thành `D:\PHAN LOAI RAC\trash-sorter-v2\.env.local`, rồi điền:
  `DEEPSEEK_API_KEY=sk-...`. File `.env.local` bị git ignore và được `scripts/start_local.ps1`
  cùng desktop `Mở Web` tự nạp trước khi bật agent.
- Chạy local một lần bằng PowerShell:
  `$env:DEEPSEEK_API_KEY="sk-..."; powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1`
- Nếu mở bằng desktop app, đặt Windows user env trước rồi mở lại app:
  `setx DEEPSEEK_API_KEY "sk-..."`
- Với production, thêm `DEEPSEEK_API_KEY` vào Vercel Production Environment rồi
  redeploy. Route `/api/user/chat` và `/api/admin/chat` gọi DeepSeek trực tiếp từ
  Vercel; chatbot không phụ thuộc máy camera hoặc hardware tunnel.
- Tùy chọn: đặt `DEEPSEEK_BASE_URL`; mặc định là `https://api.deepseek.com`.
- Model cố định là `deepseek-v4-flash` trong giai đoạn này. Không dùng
  `DEEPSEEK_MODEL` để đổi runtime model; giữ một model giúp tránh drift kiểu
  thinking-mode/empty-content của V4.
- Tùy chọn: đặt `DEEPSEEK_TIMEOUT_SECONDS`; mặc định `75`.
- Chatbot được “huấn luyện miền” bằng backend prompt profiles kết hợp EcoSort
  Knowledge/RAG local (`trash_sorter_user`, `trash_sorter_admin`), không phải hosted fine-tuning.
  Seed knowledge nằm ở `app/agent/knowledge_packs/trash_sorter_base.json`; chỉnh sửa
  của Admin lưu trong `%APPDATA%/TrashSorter/chat_knowledge.local.json`.
- Admin mở tab Account và dùng `Huấn luyện AI` để thêm/sửa snippet, bật/tắt local
  knowledge, reload file local và chạy retrieval test trước khi hỏi DeepSeek.
- Chatbot chỉ gửi aggregate counts, chart summaries, scoped history DTOs, trạng thái
  thiết bị và sanitized log counts. Nó không gửi camera frames, dataset images,
  file paths, raw logs, passwords, hashes, salts hoặc session tokens.
- Câu hỏi bản đồ dùng context `operations_map` đã sanitize. Admin thấy tất cả
  stations/bins/alerts active; User chỉ thấy station được gán cho tài khoản đó.
- Cloud User chat dùng quota nguyên tử 36 lượt mỗi tháng. Khi DeepSeek lỗi hoặc trả
  nội dung không đạt quality gate tiếng Việt có dấu, UI nhận fallback có dấu và
  không suy đoán trạng thái thiết bị.
- Advice chỉ là gợi ý lối sống/wellness tổng quát, không phải chẩn đoán y tế.

## Quy tắc camera và UART

- Chỉ dùng camera USB ngoài.
- Khi không có USB camera, preview giữ màn hình đen và `current_source=""`.
- UART chỉ bật khi chọn đúng cổng USB/Arduino thật.
- Nếu không có UART, nhận diện vẫn chạy bình thường bằng no-op sender.
- Checklist gắn mạch: `docs/hardware_integration_checklist.md`.

## Mapping 3 thùng và loa

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

## Dữ liệu và huấn luyện

Audit dataset và kiểm tra hợp đồng dữ liệu:

```powershell
python -m uv run python scripts/audit_dataset.py
```

Lệnh audit cũng kiểm tra hợp đồng YOLO `data.yaml`. Dùng strict mode trước khi
promote model để chặn drift số class, thứ tự tên class hoặc catalog:

```powershell
python -m uv run python scripts/audit_dataset.py --strict-trainset
```

Import ba dataset pen/hardware đã tải về:

```powershell
python -m uv run python scripts/import_roboflow_dataset.py --zip "$env:USERPROFILE\Downloads\PEN.v3i.yolov8.zip" --source-name roboflow_pen_v3 --label-map pen_hardware_downloads
python -m uv run python scripts/import_roboflow_dataset.py --zip "$env:USERPROFILE\Downloads\Version2.v1i.yolov8.zip" --source-name roboflow_version2 --label-map pen_hardware_downloads
python -m uv run python scripts/import_roboflow_dataset.py --zip "$env:USERPROFILE\Downloads\cardboard-paper.v1i.yolov8.zip" --source-name roboflow_cardboard_paper --label-map pen_hardware_downloads
```

Tab Data của desktop và panel Data trên web có thể lưu frame camera USB hiện tại
thành mẫu thủ công. Mẫu camera được đánh dấu cần annotation; mở màn annotate trên
web để chỉnh bbox quanh vật trước khi dùng để huấn luyện.

Luồng chụp Pen có hướng dẫn luôn tắt Actuation Test Mode và thu 24 frame qua
quality gate. Xoay hoặc dịch bút trước mỗi lần chụp. Session loại frame mờ/trùng,
giữ 6 frame holdout khóa split và để mọi mẫu ở trạng thái chờ duyệt bbox.

Manual reference đã duyệt được index bằng embedding MobileNetV3-Small. Detection
Unknown chỉ được gắn lại nhãn khi top-5 reference voting có ít nhất 3 phiếu, đạt
ngưỡng similarity và vượt runner-up margin. Ảnh holdout không bao giờ đi vào
reference index này.

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

Train nhanh candidate Pen cân bằng:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_pen_fast_training.ps1
```

Lệnh này export tối đa 4.500 ảnh theo hợp đồng 45 class cố định, giữ nguyên split
của capture session, giới hạn dữ liệu sinh thêm theo từng class, train 12 epoch
frozen ở 512px rồi 8 epoch unfrozen ở 640px. Lệnh không tự promote `models/best.pt`.

Đánh giá candidate:

```powershell
python -m uv run python scripts/evaluate_yolo.py --model runs\train\trash-sorter-v3\weights\best.pt --split test
```

Không thay `models/best.pt` bằng model mới cho tới khi candidate tốt hơn model cũ và đã test camera thật.

## Dữ liệu hiện tại

- Roboflow trusted: `13,104` ảnh.
- Tổng dataset hiện tại: `14,974` ảnh / `21,204` box.
- Class: `42`.
- Data cần duyệt: `776` item.
- Manual import hiện tại: `50` ảnh.

Các class hiếm nên bổ sung thêm data: `Aluminum caps`, `Metal shavings`, `Iron utensils`, `Wood`, `Cellulose`, `Furniture`, `Combined plastic`, `Foil`, `Ceramic`, `Plastic caps`, `Electronics`, `Scrap metal`, `Stretch film`, `Paper shavings`, `Disposable tableware`.

## Kiểm thử

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

## Đóng gói Desktop EXE

```powershell
python -m uv run python scripts/build_exe.py
```

Output nằm ở `dist/TrashSorterPro/`.

## Giao thức UART

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

Các vật viết nhỏ được route về Vô cơ:
`Pen/Pencil/Marker/Battery/Toothbrush -> R/voco/bin2`. Những class này vẫn cần
dữ liệu huấn luyện đã duyệt để YOLO nhận diện ổn định.

Khi production model còn thiếu class, desktop pipeline không im lặng: vật mới
hoặc detection confidence thấp vẫn được vẽ thành `Unknown object` và route về
đường an toàn Vô cơ `R/voco/bin2` sau khi guard cho phép. Camera-driven UART
dispatch yêu cầu Actuation Test Mode, UART đã nối, ROI hợp lệ/đang bật, vật nằm
trong ROI, nhãn ổn định, không có lượt đổ đang chạy, khay đã re-arm trống và
global cooldown đã hết. Nếu guard chặn, Live vẫn vẽ bbox và hiện trạng thái như
`ROI OFF`, `outside ROI`, `waiting stable`, `waiting empty tray`, `sort busy`
hoặc `cooldown`.

Nếu nạp firmware Arduino trong repo, có thể đổi UART protocol sang `Firmware: SORT:O/R/I`.

Board trả:

- `ACK:<cmd>`
- `NACK:<cmd>:<reason>`
- `PONG`
- `PROFILE:LEGACY_2_SERVO_OPENSMART`
- `MP3TX:<hex>` / `MP3RX:<hex>` cho chẩn đoán OPEN-SMART Serial MP3 Player A.
- `PROX:<cmd>` cho cảm biến proximity active-low chỉ dùng audio trong block profile đang chọn.
- `BIN:<bin_index>:<percent>` chỉ dùng khi firmware profile có HC-SR04, ví dụ `BIN:2:75`.
- `LOG:<text>`

## Cấu trúc chính

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

## Hồ sơ phần cứng đang dùng

Hồ sơ phần cứng thật hiện tại bám theo sơ đồ khối và ảnh board audio đỏ đã cung cấp: `LEGACY_2_SERVO_OPENSMART`.

| Nhóm | Cmd | Serial text | Thùng | Góc servo | Audio |
|---|---|---|---:|---|---:|
| Hữu cơ | O | `huuco\n` | 1 | D6=90, D7=180 | track 2 |
| Vô cơ | R | `voco\n` | 2 | D6=90, D7=0 | track 4 |
| Tái chế | I | `taiche\n` | 3 | D6=170, D7=180 | track 3 |

- Vị trí chờ/đứng sau mỗi lần đổ: D6=90, D7=85.
- Output audio mặc định là loa phần cứng OPEN-SMART. Admin có thể vào Settings ->
  Âm thanh / Loa phân loại để đổi sang `Loa máy tính` và chọn `Giọng nữ` hoặc
  `Giọng nam` cho MP3 bundled. Lựa chọn này được lưu qua các lần restart desktop.
  Loa PC phát tại thời điểm app chuẩn bị gửi UART, không chờ ACK. Ở mode loa PC,
  app gửi `SORTSILENT:<O|R|I>` để firmware chỉ chạy servo và không phát track phân loại phần cứng.
- Âm thanh khởi động: OPEN-SMART track `1`.
- Dây OPEN-SMART Serial MP3 Player A sau khi probe thực tế: Arduino TX `D5` sang MP3 RX, Arduino RX `D4` từ MP3 TX (`MP3:MODE:REVERSE`, `MP3RX` đã xác nhận). Mode D4/D5 primary cũ vẫn giữ để chẩn đoán.
- Giao thức audio: chọn TF `7E 03 35 01 EF`, đặt volume `7E 03 31 <volume> EF`, phát track `7E 04 41 00 <track> EF`.
- Cảm biến proximity là input active-low chỉ dùng audio: Hữu cơ `D10` track `5`, Tái chế `D11` track `6`, Vô cơ `D12` track `7`.
- Sự kiện cảm biến chỉ phát track `5/6/7` và publish `PROX:*`; không di chuyển D6/D7 và không tạo history row phân loại.
- Profile này không dùng cảm biến đầy HC-SR04 vì D6/D7 đang là chân servo.
- Nếu UART config đang trống và chỉ tìm thấy đúng một cổng USB/Arduino/CH340, app tự chọn và lưu cổng đó.
- UART ACK timeout mặc định `4500ms`. Firmware giữ góc đổ `1800ms`, trả về HOME theo bước 2 độ/10ms, settle `250ms`, rồi giữ cả hai servo có lực tại HOME để khay không trôi. Thời gian ACK O/R/I đo được vẫn dưới `3500ms`.
- Admin desktop/web có thể test từng thùng và xem payload, port, ACK/no ACK, thời gian phản hồi.
- Admin web có test calibration D6/D7 thô để replay vị trí candidate trước khi chốt góc production.
- Nếu UART tắt, UI hiển thị `UART OFF, không gửi xuống phần cứng`.
- Admin desktop/web có `Actuation Test Mode` cho luồng camera thật: class nhận diện -> nhóm -> thùng -> serial payload -> gửi UART -> ACK -> history row. Dùng mode này trước khi đặt vật test thật trước camera.
- Dispatch theo camera được bảo vệ bởi mặc định trong `dispatch_guard`: khi bật phân loại tự động, vật hợp lệ đầu tiên cần ổn định `2` frame cùng nhãn hiển thị; mỗi lượt đổ bị khóa cho tới ACK/NACK/timeout cộng `2.0s` settle; sau ACK/HOME camera phải thấy khay trống `2.5` giây và ít nhất `12` frame trước khi nhận vật tiếp theo, nhờ đó rung khay không tạo lượt đổ thứ hai ngay lập tức; ROI phải hợp lệ và đang bật. Nút Test Hữu cơ/Vô cơ/Tái chế vẫn là test phần cứng trực tiếp.
- Ngay trước khi gửi UART, visual safety cũng chặn detection có bbox phủ hơn `82%` frame camera hoặc crop vật sau padding có độ nét Laplacian dưới `24`. Live preview vẫn hiển thị để debug, nhưng history insertion, speaker dispatch và servo command sẽ bị chặn. Camera USB hiện tại không expose software autofocus, nên cần đặt camera xa khay hơn hoặc chỉnh focus vật lý khi Live báo `Camera bị mờ`.
