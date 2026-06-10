---
title: Local Stability Cook Pass
date: 2026-06-09
plan: "D:/PHAN LOAI RAC/plans/260609-trash-sorter-supabase-cloud-production-roadmap"
---

# Local Stability Cook Pass

## Context

User asked to proceed with `ck:cook` after the Supabase/Yolo/web/app roadmap.
Roadmap is intentionally blocked by camera/model acceptance and Arduino hardware
E2E stabilization before cloud work.

## What Happened

- Cleared stale camera and UART lock files for dead PID 3020.
- Started the local FastAPI agent with `scripts/start_local.ps1`.
- Confirmed local preflight OK with web, agent, model, and GPU available.
- Ran ruff, pytest, targeted title bar tests, mypy core, and Next.js build.
- Fixed only the ruff failure caused by intentional title bar glyphs.

## Decisions

- Supabase implementation remains deferred until local hardware gates pass.
- Mypy cleanup should be handled as a separate type-hardening task because the
  current failures span API/runtime/schema contracts.
- The agent/web local stack can stay running for manual validation.

## Next

- User accepts or adjusts Phase 1 inventory and boundaries.
- Attach USB camera and Arduino/ESP32, then rerun Phase 2 hardware-backed gates.
- Create a scoped mypy hardening phase before cloud schema work if strict type
  gates are required.
