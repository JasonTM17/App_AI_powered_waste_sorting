# 3. Lightweight IoU tracker over ByteTrack

Date: 2026-05-21

## Status

Accepted

## Context

We need to assign stable `track_id` per object across frames so that `1 object = 1 UART command`. Without tracking, every frame's detection would re-fire commands and jam the servo.

## Decision

Implement a minimal IoU + class-id matcher with `max_age` cull (`app/core/tracker.py`). Defer ByteTrack / OC-SORT to a later iteration.

## Consequences

**Positive:** Zero extra dependencies. Easy to test. Fast enough for ≤30 FPS on CPU. Clear semantics for `should_emit`/`mark_emitted` gate.
**Negative:** Less robust to occlusion or bbox jitter than learned trackers.
**Neutral:** Ultralytics' built-in BOTSORT/ByteTrack remains a swap-in option without API changes.

## Alternatives considered

- Ultralytics built-in tracker — rejected for v2.0 because per-track lifecycle hooks (emit-once gate) require either monkey-patching or wrapping anyway.
- Pure ByteTrack lib — heavy install, deepsort-style features we don't need.

## References

- ByteTrack paper https://arxiv.org/abs/2110.06864
- Ultralytics tracking docs https://docs.ultralytics.com/modes/track/
