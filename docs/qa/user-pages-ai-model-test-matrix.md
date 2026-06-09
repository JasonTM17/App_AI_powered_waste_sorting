# User Pages + AI Model QA Matrix

Date: 2026-06-08

## Scope

Validated the isolated QA stack for:

- User pages and responsive shell
- Admin/User RBAC
- DeepSeek chatbot and knowledge/RAG surfaces
- Backend history/report/auth behavior
- YOLO / 3-bin model and pipeline regression

## Result Summary

| Area | Result | Notes |
|---|---|---|
| Playwright E2E | Pass | `88` tests passed across desktop, tablet, mobile, and small mobile. |
| Backend regression | Pass | Auth, accounts, user analytics/history, chat, knowledge, and role-token regression passed. |
| Model/pipeline regression | Pass | Pipeline and 3-bin contract regression passed without touching live camera or production data. |
| Lint | Pass | `ruff check app scripts tests` clean. |
| Build | Pass | Web production build succeeded. |
| Optional live DeepSeek smoke | Skipped | Not enabled by default; QA used mocked/sanitized coverage. |

## Test Commands

| Command | Result |
|---|---|
| `python -m uv run ruff check app scripts tests` | Pass |
| `python -m uv run pytest tests/unit/test_run_agent.py -q` | Pass (`3 passed`) |
| `python -m uv run pytest tests/integration/test_agent_api.py -q -k "auth or accounts or user_analytics or user_history or user_chat or admin_chat or knowledge or role_tokens"` | Pass (`14 passed`) |
| `python -m uv run pytest tests/integration/test_pipeline_e2e.py -q` | Pass (`20 passed`) |
| `python -m uv run pytest tests/unit -q -k "waste_categories or config or inference_device or local_web or auth or three_bin"` | Pass (`41 passed`) |
| `cd web && npm run build` | Pass |
| `cd web && npm run test:e2e` | Pass (`88 passed`) |

## Browser Coverage

| Viewport | Result | Notes |
|---|---|---|
| `1440x900` | Pass | Desktop shell, admin tabs, user dashboard, and chatbot launcher remained usable. |
| `820x1180` | Pass | Tablet layout stayed readable after admin dataset-table overflow fix. |
| `390x844` | Pass | Mobile layout, bottom-safe chatbot, and user routes stayed usable. |
| `360x740` | Pass | Compact mobile stayed within width with no severe clipping. |

## Route Coverage

### Auth

| Route | Result | Notes |
|---|---|---|
| `/` | Pass | Login screen rendered; unauthorized users did not see dashboard content. |
| `forced password change` | Pass | Default-password flow still gated dashboard access. |
| `expired/invalid session` | Pass | Session handling returned the expected login state. |

### Admin

| Route | Result | Notes |
|---|---|---|
| `/admin?tab=live` | Pass | Live camera/status shell remained intact. |
| `/admin?tab=history` | Pass | History table and export flow remained accessible. |
| `/admin?tab=data` | Pass | Dataset and annotation surfaces rendered. |
| `/admin?tab=mapping` | Pass | 3-bin mapping stayed available. |
| `/admin?tab=settings` | Pass | Settings page rendered normally. |
| `/admin?tab=logs` | Pass | Logs/status surface remained accessible. |
| `/admin?tab=accounts` | Pass | Account management and AI training controls rendered. |
| `/admin?tab=reports` | Pass | Reports/export surface rendered. |

### User

| Route | Result | Notes |
|---|---|---|
| `/user/dashboard` | Pass | Core waste dashboard and range controls rendered. |
| `/user/ecopet` | Pass | Pet assistant UI rendered and stayed non-blocking. |
| `/user/advice` | Pass | Advice/Eco Score area rendered. |
| `/user/history` | Pass | Owned history rendered only for the user scope. |
| `/user/device` | Pass | Device/bin status rendered. |
| `/user/analytics` | Pass | Charts and summaries rendered. |
| `/user/reports` | Pass | Scoped report/export path worked. |
| `/user/notifications` | Pass | Local notification center rendered. |
| `/user/community` | Pass | Local community preview rendered. |
| `/user/leaderboard` | Pass | Local leaderboard/challenge view rendered. |
| `/user/account` | Pass | Account/logout surface rendered. |

## API and RBAC Coverage

| Check | Result | Notes |
|---|---|---|
| User login/session flow | Pass | QA accounts authenticated successfully against isolated temp auth DB. |
| User blocked from admin APIs | Pass | User session received `403` on admin-only surfaces. |
| Admin access retained | Pass | Admin session kept full operational access. |
| `/api/user/chat` | Pass | User chat path used sanitized owned context. |
| `/api/admin/chat` | Pass | Admin chat path used sanitized operational context. |
| Knowledge CRUD/reload/evaluate | Pass | Admin-only knowledge management regression passed. |
| User history scoping | Pass | Other-user and legacy rows stayed hidden from User views. |
| Secret handling | Pass | DeepSeek key was not printed or embedded in test artifacts. |

## Model and Pipeline Notes

- Model and pipeline regression passed without requiring a live camera or hardware.
- The 3-bin routing contract stayed conservative and consistent with the backend tests.
- No production history or auth stores were touched; all QA data lived under `web/.playwright-tmp/`.

## Artifact Paths

- Playwright report: `web/playwright-report/index.html`
- Playwright last-run marker: `web/test-results/.last-run.json`
- Isolated QA seed state: `web/.playwright-tmp/state.json`

## Notes

- Default QA runs use isolated temp data and do not require the real DeepSeek key.
- Optional real DeepSeek smoke remains behind `TRASH_SORTER_REAL_DEEPSEEK_SMOKE=1`.
- No secrets were committed as part of this QA run.
