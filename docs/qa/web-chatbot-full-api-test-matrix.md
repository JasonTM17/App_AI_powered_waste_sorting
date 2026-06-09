# Web Chatbot Full API Test Matrix

Date: 2026-06-09

## Scope

This QA pass covers the Stitch-style chatbot popup polish, User mobile routes, Admin operational routes, Auth/RBAC, DeepSeek/RAG chat contracts, and the full FastAPI route surface in `app/agent/api.py`.

Secrets were not read or printed. E2E/API tests used isolated temp `APPDATA`, temp `auth.db`, temp `history.db`, temp `dataset.db`, and mocked/no-op hardware/runtime behavior where a real device could move.

## Route Coverage

- FastAPI app routes classified: 78
- Untested/unclassified routes: 0
- New coverage file: `tests/integration/test_agent_api_full_contract.py`
- Stream/WebSocket handling:
  - `/api/camera/stream` is route-table classified and RBAC/token-denial tested for User.
  - `/ws/live` is tested with Admin accept/receive and User denial.

## API Matrix

| Area | Covered |
| --- | --- |
| Public/Auth | `/api/health`, login, logout, change-password shape through Auth regression, `/api/me` |
| User | dashboard, analytics, device, report, experience, history, export CSV, scoped image, advisor, chat |
| Admin accounts/AI | accounts list/create/reset/disable, backfill owner, knowledge CRUD/reload/evaluate, admin chat |
| Runtime/hardware | status, hardware profile/test/audio/mp3/servo/home/sort/diagnostics/reconnect, actuation test mode, devices refresh |
| Camera/live | camera start/stop via safe runtime mock, stream RBAC, websocket admin/user |
| Settings/model/mapping | settings GET/PUT, mappings GET/PUT, model classes, common waste catalog |
| Training/learn-now | training status, learn-now status/source-quality/refresh, unknown capture, micro-train blocked-safe path |
| History/logs | admin history list/export/image, logs |
| Dataset | summary, items/detail/image/boxes, sync, import, manual, camera sample, capture-session start/status/capture/stop, manual-url, web-discovery, relabel, delete, bulk, quarantine |

## Frontend Matrix

Viewports:

- Desktop: `1440x900`
- Tablet: `820x1180`
- Mobile: `390x844`
- Compact mobile: `360x740`

Routes/screens:

- Auth login and production RBAC.
- Admin tabs: live, history, data, mapping, settings, logs, accounts, reports.
- User routes: dashboard, ecopet, advice, history, device, analytics, reports, notifications, community, leaderboard, account.
- User range tabs: `7/30/90/180`, charts nonblank.
- Topbar status icons: Camera USB, AI model, Local agent popovers.
- Chatbot pet: draggable, small Stitch mascot only when closed, no fixed text bubble, prompt cloud, popup open, ESC close, outside click close, mobile-safe layout.

## DeepSeek/RAG

- Default model asserted: `deepseek-v4-flash`.
- Profiles asserted: `trash_sorter_user`, `trash_sorter_admin`.
- Missing `DEEPSEEK_API_KEY` path tested in UI and API; chatbot stays visible and returns setup guidance instead of crashing.
- User chat uses User endpoint; Admin chat uses Admin endpoint; User receives `403` for Admin chat.
- Payload tests keep context aggregate/scoped; no image/path/raw token/password/hash/salt/raw rows are sent by the tested code path.

## Commands Run

```powershell
python -m uv run pytest tests/integration/test_agent_api_full_contract.py -q
python -m uv run pytest tests/integration/test_agent_api.py -q
python -m uv run pytest tests/integration/test_pipeline_e2e.py -q
python -m uv run pytest tests/unit -q
python -m uv run ruff check app scripts tests
git check-ignore -v .env .env.local web/.env web/.env.local
git grep -n -I -E "sk-[A-Za-z0-9_-]{20,}" -- .
cd web; npm run build
cd web; npm run test:e2e
```

## Results

- Full API contract: 5 passed.
- Existing agent API regression: 63 passed.
- Pipeline/model E2E: 20 passed.
- Unit tests: 219 passed.
- Ruff: all checks passed.
- Secret hygiene: `.env`/`.env.local` ignored; no tracked real-looking `sk-*` key remains.
- Next build: compiled successfully.
- Playwright E2E: 88 passed across 4 viewports.

## Known Risks

- Real DeepSeek smoke was not run in this pass; default regression intentionally deletes `DEEPSEEK_API_KEY` unless `TRASH_SORTER_REAL_DEEPSEEK_SMOKE=1`.
- Camera stream is not consumed indefinitely in tests to avoid hanging the suite; token/RBAC and route classification are covered.
- Hardware movement is intentionally mocked/no-op in contract tests.
