# Admin web role, demo access, Supabase realtime, and keepalive

This document is the operator-facing guide for the production web dashboard at
`https://trash-sorter-v2.vercel.app`, the local Next.js dashboard, role-based
access control, and twice-weekly keepalive.

## Quick answer

- Admin and User roles are implemented in both the local FastAPI agent and the
  Vercel/Next.js cloud API.
- Admin-only API routes reject non-admin sessions with `403 Admin role is required`.
- User routes are scoped to the logged-in username through the cloud auth/session
  identity and Supabase row-level-security policies.
- Keepalive is configured twice weekly: Monday and Thursday at `03:00 UTC`.
- Real production passwords and Supabase service keys must not be committed to
  this public repository. Use disposable demo users for public testing.

## Role model

The project has two application roles:

| Role | Intended operator | Main capability |
| --- | --- | --- |
| `admin` | Maintainer, teacher, hardware operator | Manage users, devices, bin map, alerts, model settings, camera/hardware bridge, reports, training, and all history. |
| `user` | End user / demo member | View own dashboard, own history, assigned bins, alerts, collection schedule, device issue reporting, account settings, and EcoPet assistant. |

The same capability names exist in the Python agent and cloud web auth layer:

- Admin capabilities include `admin.users.manage`, `admin.roles.manage`,
  `admin.devices.manage`, `admin.bin_map.manage`, `admin.history.read_all`,
  `admin.alerts.read_all`, `admin.model.configure`, `admin.audio.configure`,
  `admin.reports.read_all`, `admin.collection_schedules.manage`, and
  `admin.device_issues.manage`.
- User capabilities include `user.bin_map.read`, `user.alerts.read`,
  `user.collection_schedule.read`, `user.collection.mark_collected`,
  `user.device_issues.create`, `user.history.read_own`, and
  `user.account.manage_own`.

## Admin dashboard functions

The Admin dashboard is served from `/admin` and uses the shared
`DashboardClient` UI.

| Admin tab | Purpose | Safety notes |
| --- | --- | --- |
| Camera | Open camera panel, stream token, hardware/local camera controls. | Production cloud can only reach hardware through the configured hardware bridge. |
| Giám sát / Live | Live detection state, current detections, status cards. | Dispatch is still guarded by local desktop/agent rules. |
| Lịch sử | Review sorting history and images when available. | Admin sees all rows; User sees own rows only. |
| Bản đồ | Manage stations, bins, coordinates, demo target selection. | Demo hardware target is optional and controlled by env flags. |
| Cảnh báo | View/acknowledge/resolve device and bin alerts. | User receives assigned alerts only. |
| Thiết bị | Create/update devices, owner username, status, active flag. | Owner mapping drives User visibility. |
| Role | Display role catalog and enabled capabilities. | Role changes are protected by Admin auth. |
| Dữ liệu | Review dataset queue, labels, trusted/untrusted state. | Do not promote unreviewed samples into training. |
| Huấn luyện | Manual training controls and dataset actions. | Production model replacement remains a deliberate release step. |
| Mapping | Map YOLO classes to three operational bins. | UART command must stay one of the supported bin commands. |
| Model AI | Inspect and configure model-related settings. | Keep runtime model hashes documented before promotion. |
| Audio | Configure/test laptop or hardware audio paths. | Hardware speaker protocol is separate from laptop PowerShell playback. |
| Cài đặt | General runtime settings. | Changes can restart camera/model workers. |
| Nhật ký | Read sanitized operational logs. | Logs must not expose tokens, DB URLs, image paths, or secrets. |
| Tài khoản | Create/disable accounts, reset passwords, backfill history owner. | Public demo accounts must be low privilege and rotated. |
| Báo cáo | Export/admin reporting. | Avoid exporting private images or credentials. |

## User dashboard functions

User routes are under `/user/dashboard` and `/user/history`.

User-facing modules include:

- overview and Eco Score;
- personal history;
- assigned station/bin map;
- alerts;
- collection schedule and mark-collected action;
- device issue reporting;
- account/password/avatar;
- EcoPet assistant;
- analytics and reports for the logged-in account.

## Screenshots

Admin screenshots:

| Accounts | Roles |
| --- | --- |
| ![Admin accounts](assets/screenshots/web-admin-accounts.png) | ![Admin roles](assets/screenshots/web-admin-roles.png) |

| Bin map |
| --- |
| ![Admin bin map](assets/screenshots/web-admin-bin-map.png) |

Existing web screenshots:

| User dashboard | Analytics |
| --- | --- |
| ![User dashboard](assets/screenshots/web-user-dashboard.png) | ![Analytics](assets/screenshots/web-analytics.png) |

| Bin map | Alerts |
| --- | --- |
| ![Bin map](assets/screenshots/web-bin-map.png) | ![Alerts](assets/screenshots/web-alerts.png) |

| EcoPet chat |
| --- |
| ![EcoPet chat](assets/screenshots/web-ecopet-chat.png) |

These Admin screenshots were captured from the local Playwright QA stack with
the seeded `qa-admin` account. They show the production UI shell and local agent
state without exposing real production credentials.

## Login accounts

### Local development accounts

When no explicit auth database is configured and local development defaults are
enabled, the local agent can seed these accounts:

| Environment | Role | Username | Password | Notes |
| --- | --- | --- | --- | --- |
| Local/dev only | Admin | `admin` | `admin123` | Enabled by `TRASH_SORTER_AUTH_DEV_DEFAULTS=1`; marked as default password. |
| Local/dev only | User | `user` | `user123` | Enabled by `TRASH_SORTER_AUTH_DEV_DEFAULTS=1`; marked as default password. |

These are not production credentials. Do not enable these defaults on public
production unless the instance is disposable.

### Playwright QA accounts

The E2E seeding script creates isolated accounts under `web/.playwright-tmp`.
They are for automated tests only and do not touch production:

| Role | Username | Password |
| --- | --- | --- |
| Admin | `qa-admin` | `QaAdmin#2026` |
| User | `qa-user` | `QaUser#2026` |
| User | `qa-other` | `QaOther#2026` |
| Temporary admin | `qa-temp-admin` | `QaTemp#2026` |

### Production demo access policy

Do not commit real Admin passwords, Supabase service-role keys, or database URLs
to this repository.

The current public production demo account is intentionally low privilege:

| Public field | Recommended value |
| --- | --- |
| Production URL | `https://trash-sorter-v2.vercel.app` |
| Public demo role | `user` |
| Public demo username | `demo-user` |
| Public demo password | `TrashSorterDemo#2026!` |
| Admin demo account | Share privately only, not in public git. |

This account has seeded demo stations/history and should be rotated whenever it
is abused or before a formal public launch. Never publish a real Admin password.

## Creating or rotating accounts

Local/dev:

```powershell
$env:TRASH_SORTER_AUTH_DEV_DEFAULTS="1"
python -m uv run python scripts/manage_auth_accounts.py list
python -m uv run python scripts/manage_auth_accounts.py create demo-user --role user --display-name "Demo User"
python -m uv run python scripts/manage_auth_accounts.py set-password demo-user
```

Production auth database:

```powershell
$env:TRASH_SORTER_AUTH_DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
python -m uv run python scripts/manage_auth_accounts.py create demo-user --role user --display-name "Demo User"
python -m uv run python scripts/manage_auth_accounts.py set-password demo-user
```

Seed persistent demo station/history data for active User accounts:

```powershell
$env:TRASH_SORTER_SUPABASE_DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
python -m uv run python scripts/seed_supabase_demo_data.py --username demo-user --apply
```

## Supabase realtime model

The Supabase migrations create:

- `profiles` with username, display name, role, and active state;
- operational tables such as devices, stations, bins, alerts, schedules,
  collection events, history, knowledge entries, and training jobs;
- `realtime_events` for bridge-compatible event fanout;
- row-level-security policies:
  - Admin can read/manage operational tables;
  - User reads assigned/owned data only;
  - realtime events are filtered by role/ownership.

The Supabase bridge syncs local desktop/agent state to cloud tables. The bridge
must run with server-side database credentials only; never expose service-role
credentials to browser code.

## Keepalive status

Keepalive is configured in both deployment config files:

| File | Cron path | Schedule |
| --- | --- | --- |
| `vercel.json` | `/api/cron/keepalive` | `0 3 * * 1,4` |
| `web/vercel.json` | `/api/cron/keepalive` | `0 3 * * 1,4` |

`0 3 * * 1,4` means Monday and Thursday at `03:00 UTC`.

The route:

1. accepts real Vercel Cron requests with `User-Agent: vercel-cron/1.0` and the
   expected `x-vercel-cron-schedule`;
2. also accepts manual verification with `Authorization: Bearer ${CRON_SECRET}`;
3. rejects non-cron/manual requests;
4. touches the configured auth/Postgres database with `select current_timestamp`;
5. touches Supabase PostgREST when `SUPABASE_URL` plus a server-side service key
   are configured;
6. returns per-target success/failure without leaking connection strings.

Production checklist:

- Set `CRON_SECRET` in Vercel Production.
- Set `TRASH_SORTER_AUTH_DATABASE_URL` or `DATABASE_URL`.
- Set `TRASH_SORTER_SUPABASE_DATABASE_URL` if Supabase DB keepalive is desired.
- Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` only as server-side env
  variables if Supabase API keepalive is desired.
- Confirm Vercel cron logs show two successful requests per week.
- Manual check after deploy: call `/api/cron/keepalive` with bearer
  `CRON_SECRET`; never paste the secret into logs or docs.

## Security boundaries

- Never commit `.env.local`, real database URLs, Supabase service-role keys,
  CRON secrets, or real production passwords.
- Public demo accounts should be `user`, not `admin`; rotate the public demo
  password if the account is abused.
- Admin accounts can create users, reset passwords, manage devices, map bins, and
  read all history; sharing an Admin password publicly is equivalent to sharing
  operational control.
- QA credentials in scripts are only safe because they write into an isolated temp
  auth store for automated tests.
