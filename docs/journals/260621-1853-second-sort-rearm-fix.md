---
title: Second sort rearm fix
date: 2026-06-21
status: completed-local
---

# Second sort rearm fix

## Context

Automatic mode sorted the first object but stayed at `waiting empty tray` for the second object, although recognition was correct.

## What happened

- Correlated the screenshot with the 18:40 runtime log and captured camera frames.
- Confirmed ACK for the first sort at 18:40:07.387, one clear empty-tray frame at 18:40:07.924, and the next bottle at 18:40:08.794.
- Found that the guard required several empty frames and discarded pending rearm evidence when the next object appeared during `RETURNING`.
- Added strict center-tray visual verification so dark side rails and full-frame false boxes do not hide a genuinely empty tray.
- Latched verified-empty evidence through `RETURNING`; ordinary no-detection frames still use the existing time/frame safety gate.

## Verification

- Real empty camera frame: verified empty.
- Real bottle camera frame: not empty.
- Focused regression suite: 24 passed.
- Ruff and Python compile checks passed.

## Decisions

- Keep the multi-frame gate for ambiguous empty observations.
- Allow a single frame only when visual empty-tray checks are strict and object-like compact detections are absent.
- Keep the new `verified_empty` parameter optional to preserve existing callers.

## Next

- Restart the desktop app so the running process loads the updated Python code.
- Perform one hardware cycle with the second object placed immediately after the tray clears.

## Unresolved questions

- None. The previously dirty recognition, tracker, UART, and visual-safety test groups now pass together.
