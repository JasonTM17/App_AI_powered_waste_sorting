# Data Quality Baseline

## Overview

Baseline captured on 2026-06-10 for Phase 1 and refreshed after Phase 3 of
`plans/data-quality-model-trust-hardening`.

Command:

```powershell
python -m uv run python scripts\audit_dataset.py --strict-trainset --blocked-reasons --quality-json dataset_v2\audit_quality_report.json
```

The command is read-only. It does not relabel, delete, quarantine, export, train,
or promote a model.

## Current Counts

| Metric | Count |
| --- | ---: |
| Queue images | 36,555 |
| Queue boxes | 53,046 |
| Catalog records | 35,255 |
| Catalog box records | 51,744 |
| Catalog classes | 50 |
| Missing metadata | 0 |
| Untrusted items | 746 |
| Trainable items by trust contract | 32,650 |
| Blocked items by trust contract | 3,905 |
| Trainable box classes | 43 |

The exported trainset contract passes the strict 45-class order check. Holdout
items are now evaluation-only and no longer counted as trainable.

## Blocking Reasons

| Reason | Count | Meaning |
| --- | ---: | --- |
| `review_required` | 1,460 | Review-required source is not approved yet or lacks `bbox_reviewed=true`. |
| `off_taxonomy` | 712 | Label does not map into the fixed 45-class training taxonomy. |
| `unknown_labels` | 712 | Metadata still carries unknown label markers. |
| `untrusted_source` | 712 | Source is `untrusted` or unknown. |
| `training_excluded` | 374 | Metadata explicitly blocks training use. |
| `invalid_bbox` | 36 | Bbox is malformed by fast coordinate validation. |
| `untrusted_meta` | 34 | Source is allowed, but the item fails trust contract validation. |

Quality-only reasons:

| Reason | Count | Meaning |
| --- | ---: | --- |
| `holdout_only` | 1,573 | Item should be treated as evaluation/holdout, not casual train data. |
| `needs_annotation` | 963 | Item still needs bbox/source review. |
| `camera_blur_augmented` | 8 | Train-only augmentation, not reference or holdout data. |

## Off-Taxonomy Labels

The catalog still contains labels outside the current training taxonomy:

- `Styrofoam`
- `Trash`
- `Trash- Brush`
- `Yoga Mat`
- `plastik`

These must be relabeled to canonical classes or quarantined before any clean
training/promotion work.

## Rare Classes Below 100 Boxes

Highest-risk weak classes include:

- `Aluminum caps`: 1
- `Metal shavings`: 1
- `Cellulose`: 3
- `Furniture`: 3
- `Combined plastic`: 4
- `Foil`: 4
- `Iron utensils`: 4
- `Ceramic`: 6
- `Plastic caps`: 9
- `Stretch film`: 9
- `Paper cups`: 30
- `Disposable tableware`: 52
- `Wood`: 64
- `Liquid`: 69

These classes need reviewed real-camera samples and holdouts before expecting
stable recognition.

## Current Decision

Do not promote or replace `models/best.pt` from the current dataset state.

Phase 3 added explicit review actions and metadata quarantine. Every item can
now resolve to one derived state: trainable, needs review, quarantine, hard
negative, holdout, or excluded, and review-required sources need both
`reviewed=true` and `bbox_reviewed=true` before training.

Phase 4 adds hard-negative capture/export as evaluation data only. Frames such
as hand-only, empty tray, cloth non-waste, two-object scenes, outside-ROI
objects, wires/fixtures, background clutter, and blur/motion are saved with
`source=hard_negative`, empty `boxes`, `training_excluded=true`, and an
`expected_outcome` for safety evaluation. Normal YOLO object-label export must
continue to skip these samples.

Safety-eval tools:

```powershell
python scripts\export_safety_eval_pack.py --queue dataset_v2\low_conf_queue --out dataset_v2\safety_eval_pack
python scripts\run_safety_eval.py --manifest dataset_v2\safety_eval_pack\manifest.jsonl --model models\best.pt --roi 255,80,820,360
```

## Report Artifact

The latest generated machine-readable report is:

```text
dataset_v2/audit_quality_report.json
```

This file is a local generated artifact and should not be treated as a source
code change unless explicitly requested.
