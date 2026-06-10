# Model Promotion Checklist

## Overview

Use this checklist before replacing `models/best.pt`. A YOLO candidate is not promotable just because training finished; it must beat the current production model on metrics and pass safety gates.

## Current Baseline

Latest software-only audit on 2026-06-09:

| Item | Value |
| --- | ---: |
| Queue images | 36,555 |
| Queue boxes | 53,046 |
| Catalog records | 35,255 |
| Box records | 51,744 |
| Catalog classes | 50 |
| Untrusted items | 712 |

Known weak/rare classes below 100 boxes include `Ceramic` 6, `Paper cups` 30, `Disposable tableware` 52, `Wood` 64, `Trash- Brush` 67, and `Liquid` 69. These classes need review before they can be trusted in production routing.

## Required Evidence

- [ ] Candidate run folder, exact command, seed/source model, image size, epochs, batch, workers, and device are documented.
- [ ] Dataset export used only trusted/reviewed training items.
- [ ] Train/valid/test splits are locked and no holdout image enters the reference index.
- [ ] Overall metrics are recorded: precision, recall, mAP50, mAP50-95.
- [ ] Per-class metrics are recorded for weak/high-risk classes.
- [ ] Empty-tray false positive test is recorded.
- [ ] Latency on target hardware is recorded.
- [ ] Real USB camera acceptance is recorded later when hardware is available.
- [ ] UART/servo acceptance is recorded later when hardware is available.
- [ ] Rollback path to previous model is documented.

## Minimum Promotion Gates

Do not promote unless all software gates pass:

| Gate | Minimum |
| --- | --- |
| Overall mAP50-95 | Better than current production candidate |
| Critical class recall | Better than current production for target weak classes |
| Empty tray false positives | 0 in the configured negative test sample |
| Unknown/low-confidence behavior | Captured for review, not silently promoted |
| Class mapping | Every new class maps to O/R/I intentionally |
| Tests/build | Ruff, focused backend tests, and web build pass |

Hardware gates remain deferred:

| Gate | Required Later |
| --- | --- |
| USB camera | Stable labels for the configured frame count inside ROI |
| Actuation | Guarded dispatch only, no repeated send loop |
| Arduino/ESP32 | ACK and bin route verified manually |

## Promotion Command Pattern

Evaluation:

```powershell
python -m uv run python scripts/evaluate_yolo.py --model runs/train/<candidate>/weights/best.pt --data dataset_v2/yolo_trainset/data.yaml --split test --device 0 --out runs/eval/<candidate>-metrics.json
```

Promotion must be a deliberate file operation with rollback, not an automatic training side effect.

## Rejection Reasons

Reject or keep as candidate when:

- Weak class recall is near zero even if overall mAP looks acceptable.
- Rare classes are trained from unreviewed or mixed-domain data.
- Empty tray produces detections.
- New classes are not mapped to the three operational bins.
- Candidate depends on a failed/partial train run.
- Real camera/hardware gates are still missing for production routing.
