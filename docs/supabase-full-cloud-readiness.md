# Supabase + Vercel Full Cloud Readiness

Date: 2026-06-17

Update: 2026-06-18

Update: 2026-06-30

## Bridge Resilience Update (2026-06-30)

- The Supabase bridge runs one sync cycle at a time and commits by domain:
  operations, demo targets, history, then training.
- Each bridge transaction sets `lock_timeout` and `statement_timeout` from:
  - `TRASH_SORTER_DB_LOCK_TIMEOUT_MS` default `2000`
  - `TRASH_SORTER_DB_STATEMENT_TIMEOUT_MS` default `15000`
- Lock-not-available, deadlock, and serialization failures retry at the domain
  transaction boundary with bounded jittered retry. Statement timeout,
  authentication, and schema errors fail the cycle clearly instead of retrying
  forever.
- Conflict upserts skip unchanged rows with `IS DISTINCT FROM` where possible,
  so timestamps only move when business data changes.
- A successful sync writes a heartbeat. Docker healthcheck verifies process
  health and heartbeat freshness.

## User Cloud Dashboard Update (2026-06-18)

- Production User analytics, history, device, report, experience, advisor, and
  CSV export now read scoped Supabase data through authenticated Next.js routes.
- Every query derives `owner_username` from the verified session. Browser query
  parameters cannot switch account scope.
- The hardware bridge retries history uploads with `(device_id,
  local_history_id)` and skips rows that do not have an owner instead of
  publishing unassigned history.
- A valid saved session is visibly restored; an expired token is removed before
  returning to login. User routes continue to redirect away from Admin pages.
- Production browser code blocks direct local-agent calls. Admin camera and
  training remain available only through the allowlisted HTTPS hardware bridge.
- A User without assigned hardware receives a completed empty dashboard and
  the message `Chưa được gán thiết bị`, never another User's data.

## Architecture

- Vercel hosts the Next.js web app.
- Supabase owns cloud Postgres/RLS, Storage later, and Realtime subscriptions.
- Vercel serves a small cloud auth API for `/api/auth/login`, `/api/me`,
  `/api/auth/logout`, and `/api/auth/change-password` against the shared
  `accounts`/`sessions` tables. This lets the deployed web login without a
  running local agent.
- The Windows machine attached to USB camera/UART remains the hardware bridge.
- Browser users never receive service-role secrets, camera stream tokens, UART controls, or training controls unless they are Admin through the local/admin API surface.

## Supabase Setup

1. Create a Supabase project and apply `supabase/migrations/202606170001_full_cloud_readiness.sql`.
2. Enable RLS on every exposed table; the migration does this by default.
3. Create one `profiles` row per Supabase Auth user:
   - `role='admin'` for operators.
   - `role='user'` for field/user accounts.
4. Apply/create the local-agent auth tables in Supabase Postgres (`accounts`,
   `sessions`, `chat_usage`) by running the local agent or auth management
   scripts with `TRASH_SORTER_AUTH_DATABASE_URL` pointed at Supabase.
5. On Vercel, set server-side auth database variables:
   - `TRASH_SORTER_AUTH_DATABASE_URL`
   - `DATABASE_URL` as a fallback with the same pooled/direct Postgres URL
   - `DEEPSEEK_API_KEY` for production `/api/user/chat` and `/api/admin/chat`
   - Optional `DEEPSEEK_BASE_URL` and `DEEPSEEK_TIMEOUT_SECONDS`
6. On Vercel, set browser-safe variables only when cloud UI reads Supabase
   directly:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_AGENT_URL` only when the deployed web must still call a reachable agent. If omitted in production, the web uses the Vercel origin for cloud auth routes.
7. On the local hardware machine, set only server-side bridge secrets:
   - `TRASH_SORTER_SUPABASE_DATABASE_URL`
   - Optional existing local-agent vars such as `TRASH_SORTER_AUTH_DATABASE_URL`, `DATABASE_URL`, and `DEEPSEEK_API_KEY`.

The Vercel chat routes call DeepSeek server-side and read only role-scoped aggregate
history, map, alert, schedule, and enabled knowledge data. They never send session
tokens, database credentials, raw logs, image paths, or hardware secrets. User chat
shares the existing `chat_usage` table and enforces 36 requests per calendar month.
Chat responses use SSE (`meta`, `delta`, `done`, and safe `error` events) so the UI
renders the first provider tokens without waiting for the complete answer.

## Hardware Bridge

Run from the project root:

```powershell
$env:TRASH_SORTER_SUPABASE_DATABASE_URL="postgresql://..."
python -m uv run python scripts/supabase_hardware_bridge.py --once
python -m uv run python scripts/supabase_hardware_bridge.py --interval 10
```

The bridge syncs:

- `devices`
- `bin_stations`
- `bins`
- `alerts`
- safe `history` metadata
- current `training_jobs` status metadata

It does not publish camera frames, local file paths, dataset images, passwords,
session tokens, raw logs, or any endpoint for User-triggered camera/training
actions.

## Teacher Demo Data

Preview the persistent seed without writing:

```powershell
python -m uv run python scripts/seed_supabase_demo_data.py
```

Apply it after setting `TRASH_SORTER_SUPABASE_DATABASE_URL` or `POSTGRES_URL`:

```powershell
python -m uv run python scripts/seed_supabase_demo_data.py --apply
```

Apply `supabase/migrations/202606180005_performance_demo_seed.sql` before the
current seed. Each active User receives three assigned stations, nine child bins,
one online demo device, collection/alert records, and 240 deterministic,
idempotent history rows spanning 180 days. Set
`NEXT_PUBLIC_DEMO_HARDWARE_TARGET=1` on Vercel and
`TRASH_SORTER_DEMO_HARDWARE_TARGET=1` on the hardware bridge. The latest bin
selected on the map receives the next local fullness reading; `95%` or higher
is stored as `full` and displayed as `Đã đầy`.

## Role Contract

Admin:

- Read/manage devices, bin map, alerts, schedules, issues, history, knowledge, and training metadata.
- Use local/admin APIs for camera, dataset, settings, model, audio, UART, and training controls.

User:

- Read only assigned active stations, child bins, alerts, schedules, own history, and role-allowed knowledge.
- Insert only assigned collection events and device issues.
- Cannot update roles, model, audio, device inventory, global map metadata, training jobs, camera stream, dataset, settings, logs, or admin APIs.

## Realtime Contract

The migration writes narrow events to `public.realtime_events`:

- `bin_status_changed`
- `alert_created`
- `alert_resolved`
- `collection_completed`
- `device_issue_created`
- `device_status_changed`

Frontend code should subscribe to this table or mirror these rows into Supabase
Broadcast. Payloads intentionally contain IDs/status values, not raw row dumps.

## User Cloud API

- `GET /api/user/analytics?range_days=7|30|90|180`
- `GET /api/user/history?limit=&offset=&range_days=`
- `GET /api/user/device`
- `GET /api/user/report?range_days=`
- `GET /api/user/experience?range_days=`
- `GET /api/user/dashboard-summary?range_days=7|30|90|180`
- `POST /api/user/advisor`
- `GET /api/user/history/export.csv?range_days=`

These routes require an active User session. Missing sessions return `401`,
non-User sessions return `403`, and all database reads use the session username.
The dashboard uses the summary route to authenticate once and reuse one analytics
aggregate for report and experience output; the individual routes remain available
for dedicated screens and backward compatibility.

## Deployment Gate

Before deploying:

```powershell
python -m uv run pytest -q
cd web
npm run build
npm run test:e2e
```

Also manually verify:

- User account cannot open `/admin?tab=training`.
- User token receives 403 from camera/training/dataset/settings/model/log APIs.
- Map marker popup shows `Đã đầy` when a bin reaches `95%` or status `full`.
- Supabase RLS tests confirm User can read only assigned rows.
- Ask EcoPet `Hôm nay bạn thế nào?` and confirm the reply is relevant Vietnamese
  with diacritics, not the hardware bridge fallback.
- Temporarily test an invalid AI key in Preview and confirm the response is the
  accented safe fallback without exposing the key or provider response body.
