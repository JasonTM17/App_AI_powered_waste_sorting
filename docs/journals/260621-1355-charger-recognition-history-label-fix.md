---
title: Charger recognition and history label fix
date: 2026-06-21
status: completed-local
---

# Charger recognition and history label fix

## Context

Live camera labeled a wall charger as `Bút bi 0.55`. Earlier captured objects also contained unreliable display labels.

## What happened

- Reproduced the charger frame: base model saw weak `Electronics`, specialist emitted stronger `Pen`.
- Confirmed specialist model has no wall-charger class; the configured route existed but was inactive.
- Added a minimum bounding-box aspect ratio for elongated classes. Charger-shaped boxes can no longer become `Pen` through the specialist model.
- Promoted four consecutive user-confirmed charger frames to audited, recognition-only references: `Cục sạc` / `Electronics`.
- Added immutable raw class plus normalized display label, review status/source/confidence and audit metadata to Desktop, bridge and Web history.
- Backed up and backfilled 774 local rows. Ambiguous captured images moved to Admin review instead of receiving guessed labels.

## Verification

- Exact charger pipeline result: `Cục sạc` → `Electronics` → `Vô cơ` → bin 2.
- Python focused suite: 129 passed. Agent API contract: 5 passed.
- Web: 82 passed, 1 intentional skip; TypeScript check and production build passed.
- Backfill second run: 0 changes. Immutable data comparison: 0 changed rows.

## Decisions

- Do not rewrite `cls_name`; preserve model evidence.
- Do not train from UI screenshots or unreviewed queue frames.
- Do not invent a specific object label when the image is absent, blurred or disputed.
- Cloud migration and production deployment remain separate from this local data operation.

## Next

- Apply migration `202606210008_history_review_labels.sql` before cloud review is enabled.
- Admin reviews the 138 disputed image rows from Desktop or Web.

## Unresolved questions

- Production migration/deployment requires a verified cloud connection and deployment credentials.
