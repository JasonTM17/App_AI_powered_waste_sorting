# Supabase + Vercel Full Cloud Readiness

Date: 2026-06-17

## Architecture

- Vercel hosts the Next.js web app.
- Supabase owns cloud Auth, Postgres, RLS, Storage later, and Realtime subscriptions.
- The Windows machine attached to USB camera/UART remains the hardware bridge.
- Browser users never receive service-role secrets, camera stream tokens, UART controls, or training controls unless they are Admin through the local/admin API surface.

## Supabase Setup

1. Create a Supabase project and apply `supabase/migrations/202606170001_full_cloud_readiness.sql`.
2. Enable RLS on every exposed table; the migration does this by default.
3. Create one `profiles` row per Supabase Auth user:
   - `role='admin'` for operators.
   - `role='user'` for field/user accounts.
4. On Vercel, set only browser-safe variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_AGENT_URL` only when the deployed web must still call a reachable agent.
5. On the local hardware machine, set only server-side bridge secrets:
   - `TRASH_SORTER_SUPABASE_DATABASE_URL`
   - Optional existing local-agent vars such as `TRASH_SORTER_AUTH_DATABASE_URL`, `DATABASE_URL`, and `DEEPSEEK_API_KEY`.

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
