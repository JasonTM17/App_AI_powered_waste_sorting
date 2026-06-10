# Operations Map Local-First Handoff

Date: 2026-06-10

## Scope

This document freezes the local operations contract for the real bin map,
alerts, collection schedule, mark-collected flow, and device issue reporting.
Supabase, RLS, migrations, Edge Functions, and realtime channels are deferred
until the local app remains green across backend, web build, E2E, and preflight.

## Local Store

The local agent owns `%APPDATA%/TrashSorter/operations.db` through SQLAlchemy.
The store is safe to initialize with no camera, UART, audio device, Supabase, or
internet map tiles.

Tables:

| Local table | Purpose |
|---|---|
| `devices` | Local device inventory and health/status metadata. |
| `bin_stations` | Map station records with editable latitude/longitude. |
| `bins` | Child bins under each station: organic, recyclable, inorganic. |
| `collection_schedules` | Assigned/scoped collection work items. |
| `collection_events` | Audit trail for completed collections. |
| `alerts` | Operational alerts, including issue-derived alerts. |
| `device_issues` | User/admin issue reports for hardware or station problems. |

Seed behavior:

- First clean startup creates 10 Thu Duc candidate stations.
- Each station creates 3 child bins: `O/bin1`, `R/bin2`, and `I/bin3`.
- Seed stations are editable starter data, not official public-bin inventory.
- `coordinate_verified=false` until Admin confirms the location after survey.
- Default map center is `10.843195, 106.777800`, zoom `12`.

## Role Contract

Admin capabilities:

- `admin.users.manage`
- `admin.roles.manage`
- `admin.devices.manage`
- `admin.bin_map.manage`
- `admin.history.read_all`
- `admin.alerts.read_all`
- `admin.model.configure`
- `admin.audio.configure`
- `admin.reports.read_all`
- `admin.collection_schedules.manage`
- `admin.device_issues.manage`

User capabilities:

- `user_dashboard`
- `user.bin_map.read`
- `user.alerts.read`
- `user.collection_schedule.read`
- `user.collection.mark_collected`
- `user.device_issues.create`
- `user.history.read_own`
- `user.account.manage_own`

Backend gates own authorization. Frontend nav must not be treated as security.

## Local API Contract

Admin:

- `GET /api/admin/roles`
- `GET /api/admin/devices`
- `POST /api/admin/devices`
- `GET /api/admin/bin-map`
- `POST /api/admin/bin-map`
- `PATCH /api/admin/bin-map/{station_id}`
- `DELETE /api/admin/bin-map/{station_id}`
- `GET /api/admin/alerts`
- `PATCH /api/admin/alerts/{alert_id}`
- `GET /api/admin/collection-schedules`
- `GET /api/admin/operations/health`

User:

- `GET /api/user/bin-map`
- `GET /api/user/alerts`
- `GET /api/user/collection-schedule`
- `POST /api/user/collections/{schedule_id}/complete`
- `POST /api/user/device-issues`

Contract rules:

- Admin can read/manage global operation data.
- User sees scoped active stations, alerts, schedules, own history, and own
  account data only.
- Duplicate collection completion is idempotent and returns an already-complete
  state rather than creating duplicate events.
- Device issue creation creates a corresponding admin-visible alert.
- None of these endpoints sends UART, servo, camera, or audio commands.

## Future Supabase Mapping

| Local concept | Future Supabase table | Notes |
|---|---|---|
| `devices` | `devices` | Include organization/project scope, status, last seen, owner metadata. |
| `bin_stations` | `bin_stations` | Keep lat/lng, verification flag, active flag, area, and station metadata. |
| `bins` | `bins` | Keep station FK, bin code, waste type, fill status, sensor status. |
| `collection_schedules` | `collection_schedules` | Keep assignment scope, due window, status, station/bin FKs. |
| `collection_events` | `collection_events` | Append-only audit trail for mark-collected actions. |
| `alerts` | `alerts` | Normalize severity, source, station/bin/device FKs, status, resolver. |
| `device_issues` | `device_issues` | Preserve reporter, issue type, description, status, linked alert. |
| capabilities | `profiles`/auth claims + RLS | Capabilities must mirror the local role matrix. |

Backfill requirements before migration:

1. Export local `operations.db` rows with stable UUID/string IDs preserved.
2. Preserve `coordinate_verified=false` for all unverified Thu Duc seeds.
3. Preserve collection event timestamps and actor usernames.
4. Link issue-derived alerts to their source issue where possible.
5. Keep local IDs as external IDs if Supabase generates new primary keys.

## RLS Requirements

Admin policies:

- Admin can read all project-scoped operation rows.
- Admin can insert/update/deactivate devices, stations, bins, schedules, alerts,
  and issue status.
- Admin can read all history/report data for the project.

User policies:

- User can read assigned/scoped active stations and child bins.
- User can read assigned/scoped alerts and schedules.
- User can insert collection completions only for assigned/scoped schedules.
- User can insert device issues only for scoped stations/devices.
- User can read own collection events and own issue reports.
- User cannot update role, model, audio, device inventory, or global map
  metadata.

Every exposed table must have RLS enabled before frontend cloud access exists.

## Future Realtime Contract

Realtime should use narrow payloads, not full table broadcasts:

```json
{"event":"bin_status_changed","station_id":"td-bin-001","bin_code":"O/bin1","fill_status":"high"}
{"event":"alert_created","alert_id":"alert_123","severity":"warning","station_id":"td-bin-002"}
{"event":"alert_resolved","alert_id":"alert_123","resolved_by":"admin"}
{"event":"collection_completed","schedule_id":"sched_123","completed_by":"user"}
{"event":"device_issue_created","issue_id":"issue_123","station_id":"td-bin-003"}
{"event":"device_status_changed","device_id":"local-sorter-001","status":"offline"}
```

Recommended channels later:

- `project:{project_id}:operations`
- `project:{project_id}:alerts`
- `user:{user_id}:assignments`

## Validation Snapshot

Local core validation passed on 2026-06-10:

- `python -m uv run ruff check app scripts tests`
- `python -m uv run pytest -q`
- `python -m uv run python scripts/preflight_runtime.py`
- `cd web && npm run build`
- `cd web && npm run test:e2e`

Supabase work may start only after these gates are re-run and still pass.
