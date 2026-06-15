# Blank Tray, Bagasse, And Live UI Fix

## Problems

- A nearly uniform empty tray could be detected as `Paper` or generic recyclable waste.
- Sugarcane bagasse was confused with `Paper bag` even when YOLO also saw `Organic`.
- Live bbox exposed the internal label `Kaggle 3-bin O`.
- The AI Detection column consumed more horizontal space than needed.

## Decisions

- Reject large detections on a visually uniform, low-detail tray before fallback and tracking.
- Correct a paper-like result to `Organic` only when YOLO also sees overlapping `Organic`
  with a compatible score and the independent three-bin classifier confirms route `O`.
- Store the bagasse ambiguity correction as canonical class `Organic` with class id `17`.
- Present unresolved `O/R/I` outputs as Vietnamese waste groups, never as Kaggle internals.
- Increase the Live camera-to-detection layout ratio from `3:1` to `4:1`.
- Reduce post-HOME settle from `1.0s` to `0.35s`; active servo motion remains unchanged.

## Verification

- Unit and focused integration tests cover blank tray suppression, bagasse routing,
  canonical Organic output, label presentation, dispatch re-arm, and fast settle.
- The current camera frame produced overlapping `Paper bag` and `Organic`; the secondary
  classifier confirmed `O`, so the corrected output is `Organic`.
- Curated Organic aliases include banana/fruit peel, vegetable and food scraps,
  eggshell, coffee/tea grounds, leaves, hard fruit rind, bones, and sugarcane bagasse.
- Generic three-bin `O` remains `Rác hữu cơ (chưa xác định loại)`; it is not promoted to
  the exact `Organic` class unless the narrow two-model bagasse ambiguity gate passes.

## Unresolved Questions

- Exact bagasse recognition still needs reviewed bagasse samples and a future trained class
  if the operator wants a label more specific than `Organic`.
