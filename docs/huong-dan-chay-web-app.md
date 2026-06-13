# Hướng Dẫn Chạy Web App Trash Sorter Pro

Tài liệu này dành cho đồng nghiệp clone repo về chạy web dashboard trên máy Windows.
Web app là giao diện Next.js, nhưng phải chạy cùng local FastAPI agent của project để có API đăng nhập, camera, lịch sử, mapping và cấu hình.

## 1. Yêu cầu cài đặt

- Windows 10/11.
- Python 3.10 đến 3.12.
- `uv` cho Python:

```powershell
python -m pip install uv
```

- Node.js 20 trở lên, kèm `npm`.
- Git.
- Nếu muốn chạy nhận diện thật, cần có 2 model trong repo:

```powershell
Test-Path models/best.pt
Test-Path models/new-class-specialist.pt
```

Cả hai lệnh phải trả về `True`.

## 2. Clone repo

```powershell
git clone https://github.com/JasonTM17/App_AI_powered_waste_sorting.git
cd App_AI_powered_waste_sorting
```

Nếu đang làm trực tiếp trên máy này thì thư mục hiện tại là:

```powershell
cd "D:\PHAN LOAI RAC\trash-sorter-v2"
```

## 3. Cài dependency

Chạy từ thư mục gốc repo:

```powershell
python -m uv sync --frozen
cd web
npm ci
cd ..
```

Không commit các thư mục sinh ra sau khi cài:

- `.venv/`
- `web/node_modules/`
- `web/.next/`
- `dist/`
- `build/`

Những thư mục này đã được ignore sẵn.

## 4. Cấu hình môi trường

### Cách nhanh để chạy local

Nếu chỉ muốn chạy local để xem web, có thể không tạo file env. Script sẽ tự bật tài khoản dev mặc định khi chưa có cấu hình DB sản xuất:

- Admin: `admin` / `admin123`
- User: `user` / `user123`

Tài khoản dev có thể bị yêu cầu đổi mật khẩu sau lần đăng nhập đầu tiên.

### Cách dùng PostgreSQL

Nếu dùng PostgreSQL thật, tạo file `.env.local` ở thư mục gốc repo:

```powershell
Copy-Item .env.example .env.local
notepad .env.local
```

Điền các biến cần thiết:

```dotenv
TRASH_SORTER_AUTH_DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE
TRASH_SORTER_ALLOWED_ORIGINS=http://localhost:3000
```

Lưu ý:

- Không commit `.env.local`.
- Không đưa mật khẩu DB, API key, token lên git.
- Nếu dùng Supabase/PostgreSQL pooler, dùng đúng connection string mà team đang quản lý.

### DeepSeek chatbot nếu cần

Thêm vào `.env.local`:

```dotenv
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_TIMEOUT_SECONDS=75
```

Không đặt DeepSeek key trong `web/.env.local` với tiền tố `NEXT_PUBLIC_`, vì như vậy key sẽ lộ ra frontend.

## 5. Chạy web app bằng một lệnh

Chạy từ thư mục gốc repo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1
```

Script này sẽ:

- Nạp `.env` và `.env.local` nếu có.
- Cài Python venv bằng `uv sync --frozen` nếu thiếu.
- Cài web dependency bằng `npm ci` nếu thiếu.
- Kiểm tra model runtime.
- Chạy FastAPI agent tại `http://127.0.0.1:8765`.
- Chạy Next.js web tại `http://127.0.0.1:3000`.
- Tự dừng agent cũ của repo nếu bị treo và có nguy cơ giữ lock camera/UART.

Mở trình duyệt:

```text
http://127.0.0.1:3000
```

## 6. Chạy thủ công từng phần

Dùng cách này khi cần xem log trực tiếp.

Terminal 1, chạy agent:

```powershell
python -m uv run python scripts/run_agent.py
```

Terminal 2, chạy web:

```powershell
cd web
npm run dev
```

Địa chỉ mặc định:

- Agent: `http://127.0.0.1:8765`
- Web: `http://127.0.0.1:3000`

Nếu đổi port agent, cập nhật `NEXT_PUBLIC_AGENT_URL` trong `web/.env.local`:

```dotenv
NEXT_PUBLIC_AGENT_URL=http://localhost:8765
```

## 7. Kiểm tra trước khi đưa cho người khác

Chạy Python test liên quan desktop/core:

```powershell
python -m uv run pytest
```

Chạy lint/test/build web:

```powershell
cd web
npm run test:unit -- --run
npm run build
cd ..
```

Nếu chỉ muốn smoke check nhanh:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1
```

Sau đó mở:

```text
http://127.0.0.1:3000
```

## 8. Đăng nhập và vai trò

- Admin: vào được camera/live, data, mapping, settings, logs, account và train AI.
- User: chỉ thấy dashboard người dùng, thùng rác, lịch sử của tài khoản, thông báo và báo cáo.

Với PostgreSQL, tài khoản nằm trong DB. Nếu không nhớ mật khẩu admin, không đoán mật khẩu. Hãy tạo hoặc reset bằng script quản lý tài khoản theo quy trình team:

```powershell
python -m uv run python scripts/manage_auth_accounts.py create owner --role admin --force-change
python -m uv run python scripts/manage_auth_accounts.py set-password owner
```

## 9. Lỗi thường gặp

### Web mở được nhưng login báo lỗi

Kiểm tra agent có chạy không:

```powershell
Invoke-WebRequest http://127.0.0.1:8765/api/health -UseBasicParsing
```

Nếu dùng PostgreSQL, kiểm tra `.env.local` có đúng connection string không.

### Camera đen hoặc không có frame

- Cần USB camera ngoài, app không fallback sang webcam laptop.
- Đóng các app đang giữ camera.
- Chạy lại `scripts/start_local.ps1` để dọn agent cũ có thể đang giữ lock.

### Port 3000 hoặc 8765 bị chiếm

Dùng port khác:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1 -AgentPort 8766 -WebPort 3001
```

Nếu đổi `AgentPort`, nhớ đặt `NEXT_PUBLIC_AGENT_URL` cho web tương ứng.

### Thiếu model

Kiểm tra:

```powershell
Test-Path models/best.pt
Test-Path models/new-class-specialist.pt
```

Nếu một trong hai lệnh là `False`, pull lại repo hoặc lấy model runtime từ người phụ trách.

## 10. Checklist bàn giao

Trước khi báo đồng nghiệp test:

- `git status` sạch hoặc chỉ có thay đổi riêng của bạn.
- `models/best.pt` và `models/new-class-specialist.pt` tồn tại.
- `python -m uv sync --frozen` thành công.
- `npm ci` trong thư mục `web` thành công.
- `npm run build` trong thư mục `web` thành công.
- `scripts/start_local.ps1` mở được agent và web.
- Không commit `.env.local`, DB local, log, capture ảnh thật, dataset tạm, `dist/`, `.venv/`, `node_modules/`.
