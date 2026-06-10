# Core Readiness Handoff

Date: 2026-06-10

## Scope Locked

Implemented scope is local core only:

- Included: phases 1-7 and 10-11 of the master roadmap.
- Deferred: Supabase foundation, realtime channels, remote actions, migrations, RLS, Edge Functions.
- Deferred: real USB camera, Arduino/UART, and audio hardware acceptance.
- Frozen: EcoPet visual files and chat launcher appearance.
- Added: local role permissions, operations DB, Thu Duc bin map, alerts,
  collection schedules, mark-collected flow, and device issue reporting.

## Current Contracts

- DeepSeek runtime is fixed to `deepseek-v4-flash`; thinking mode is disabled in backend payloads.
- API keys stay in the local FastAPI agent environment, never in frontend `NEXT_PUBLIC_*`.
- Chatbot context is sanitized to aggregate/device-safe data.
- Desktop and preflight smoke tests do not require real camera, UART, or audio hardware.
- YOLO model promotion is blocked unless class contract, metrics, and acceptance evidence are present.
- `operations.db` is local-only and seeded with 10 Thu Duc candidate stations,
  each with `O/bin1`, `R/bin2`, and `I/bin3`; Admin must verify coordinates later.
- User operations are scoped to map, alerts, schedule, collect, issue report,
  own history, and own account. Admin operations include roles, devices, bin map,
  alerts, schedules, model, audio, and reports.
- Supabase handoff contract is documented in
  [`docs/operations-map-local-first.md`](operations-map-local-first.md), covering
  local tables, DTO/API ownership, future table mapping, RLS requirements, and
  realtime payloads without adding Supabase code.

## Core Commands

```powershell
cd "D:\PHAN LOAI RAC\trash-sorter-v2"
python -m uv sync
python -m uv run python -m app
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1
```

## Verification Gates

```powershell
python -m uv run ruff check app scripts tests
python -m uv run pytest -q
python -m uv run python scripts/audit_dataset.py
python -m uv run python scripts/audit_dataset.py --strict-trainset
python -m uv run python scripts/preflight_runtime.py
cd web
npm run build
npm run test:e2e
```

`audit_dataset.py --strict-trainset` is intentionally allowed to fail when catalog
classes drift from `dataset_v2/yolo_trainset/data.yaml`. Treat that as a model
promotion blocker, not as a reason to force-promote a candidate.

## Continue Sequence

1. Finish all local tests and web route checks.
2. Review the YOLO audit output and fix class drift through reviewed data or mapping changes.
3. Promote a model only after `docs/model_promotion_checklist.md` is complete.
4. Run real hardware acceptance later with USB camera/UART/audio connected.
5. Start Supabase only after local core gates stay green and the
   `operations-map-local-first.md` mapping is accepted as the schema/RLS source.

## Unresolved Questions

None for the local-core scope. Supabase schema and real hardware acceptance remain deferred by user request.
