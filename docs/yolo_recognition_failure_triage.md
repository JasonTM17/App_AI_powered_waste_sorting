# YOLO Recognition Failure Triage

## Overview

When YOLO nhận diện không ổn, do not immediately retrain or replace the model. Classify the failure first. Most recognition problems come from data quality, camera domain mismatch, thresholds, ROI, or routing logic.

## Fast Decision Tree

1. Is the object visible and sharp in the tray?
   - No: fix lighting, focus, motion blur, crop, or camera placement.
   - Yes: continue.

2. Is the object inside the dispatch ROI?
   - No: fix ROI or reject dispatch outside ROI.
   - Yes: continue.

3. Does YOLO detect anything with a low confidence floor?
   - No: likely missing class/domain data.
   - Yes: inspect class, confidence, bbox, and competing classes.

4. Is the class rare or weak in the dataset?
   - Yes: collect reviewed real-camera samples and holdouts.
   - No: inspect labels, duplicates, and thresholds.

5. Is the model right visually but routed wrong?
   - Fix mapping O/R/I, not the model.

6. Does empty tray produce detections?
   - Treat as safety blocker. Tune thresholds/ROI/negative samples before any promotion.

## Failure Categories

| Category | Signal | Fix |
| --- | --- | --- |
| Bad label | Correct object, wrong class in training data | Review labels and remove bad samples |
| Weak class | Very low boxes or recall | Add reviewed real-camera samples and holdouts |
| Domain mismatch | Works on dataset, fails on real tray | Capture local tray-camera data |
| Blur/lighting | Box jumps or confidence unstable | Improve lighting, camera mount, exposure |
| ROI issue | Object outside accepted area | Tune ROI and dispatch guard |
| Threshold issue | Correct class appears but never routes | Tune per-class thresholds |
| Empty-tray false positive | Detection without object | Add negatives, raise thresholds, block promotion |
| Mapping issue | Detection right, bin wrong | Fix class-to-O/R/I mapping |
| Tracker instability | Label flips frame to frame | Require stable-frame voting before dispatch |

## Current Dataset Findings

Software-only audit on 2026-06-09 showed:

- 36,555 queue images and 53,046 queue boxes.
- 35,255 catalog records and 51,744 catalog box records.
- 712 untrusted items.
- 50 catalog classes while the current exported YOLO trainset declares 45 classes.
- Several weak classes are below 100 boxes, including `Ceramic`, `Paper cups`, `Disposable tableware`, `Wood`, `Trash- Brush`, and `Liquid`.

This means the next YOLO work should focus on source quality and per-class review before more full training.

## What To Do First

Run:

```powershell
python -m uv run python scripts/audit_dataset.py
```

Then inspect:

- Rare classes under 100 boxes.
- `untrusted` count.
- Whether target weak classes have reviewed real-camera samples.
- Whether trainset class count matches the intended model output.

## What Not To Do

- Do not promote `models/best.pt` from a partial or smoke run.
- Do not train unreviewed low-confidence captures directly.
- Do not solve a mapping/bin problem by retraining YOLO.
- Do not route uncertain detections silently.
- Do not use Supabase or Realtime to compensate for local recognition instability.

## Next Hardware-Deferred Tests

When USB camera and Arduino/ESP32 are available:

- Empty tray negative run.
- Object held inside ROI.
- Object removed and tray re-armed.
- Object outside ROI.
- Multi-object warning.
- Guarded dispatch with ACK and no repeated UART loop.
