---
date: 2026-06-10
topic: dispatch-data-trust-safety
source_plan: plans/desktop-app-data-auth-stabilization-continuation
---

# Dispatch Data Trust Safety

## Context

Manual testing showed the desktop app could present hand/cloth/unknown scenes as
sortable waste, and history/export behavior made the dataset look healthier than
it was.

## What Happened

- Runtime dispatch now refuses more than one object in ROI, including same-class
  pairs.
- `Unknown object` no longer falls through to bin `R` by default.
- Agent live DTO no longer exposes a fake unknown route unless explicitly
  enabled.
- YOLO export now writes canonical 45-class `data.yaml` and records model class
  mismatches in the export report.
- Safety eval `two_objects` now means two detections, not only two distinct
  classes.

## Decisions

- Prefer safe refusal over fallback sorting for unknowns.
- Keep `multiple waste types` as the existing status string for compatibility,
  while broadening the logic to multiple objects.
- Keep model training class order independent of the currently loaded model file.

## Next

- Capture real hard negatives from camera: hand-only, cloth, empty tray,
  outside-ROI, two objects.
- Add promotion gate before any `models/best.pt` overwrite.
- Finish shared Supabase auth runtime once the local PostgreSQL URL is supplied.
