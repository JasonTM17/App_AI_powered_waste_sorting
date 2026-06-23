---
title: Desktop web link fix
date: 2026-06-23
type: journal
---

# Desktop Web Link Fix

## Context

Desktop title bar button `Mở Web` should open production dashboard:
`https://trash-sorter-v2.vercel.app/admin?tab=live`.

## What Happened

- Kept launcher production-first behavior.
- Added URL normalization so requested tab is applied without dropping path or other query params.
- Added browser fallback when Qt desktop URL open returns false.
- Added focused unit coverage for production URL and custom query preservation.

## Decisions

- No camera, AI, UART, auth, or web dashboard logic changed.
- No docs update beyond this journal; behavior change is launcher-only.

## Next

Unresolved questions: none.
