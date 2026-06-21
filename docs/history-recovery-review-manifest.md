# History Recovery Review Manifest

This file is generated from preserved camera history and queue metadata.
Old history labels are model predictions, not human ground truth.

## Summary

- Queue: `dataset_v2\low_conf_queue`
- Audit source: `runs\eval\history-capture-model-audit.json`
- Restored captures: 156
- High priority review: 115
- Medium priority review: 41
- Exact label drift: 82
- Route/bin drift: 56
- Manual candidate notes: 4
- Manual quarantine notes: 4

## Review Rules

- Do not train from any `history_recovery_*.jpg` until Admin reviews label and bbox.
- Keep `training_excluded=true` and `recognition_enabled=false` for unreviewed images.
- Quarantine no-camera, hand-covered, blank, or unclear frames.
- For clear objects, correct the full-object bbox before enabling as reference/training.
- Battery/pin samples must be marked hazardous and must not auto-sort.

## Top Old Labels

| Old model label | count |
| --- | ---: |
| Organic | 33 |
| Aluminum can | 15 |
| Unknown object | 15 |
| Tin | 13 |
| Paper | 10 |
| Pen | 10 |
| Printing industry | 9 |
| Plastic bottle | 8 |
| Plastic bag | 7 |
| Kaggle 3-bin I | 7 |
| Glass bottle | 7 |
| Plastic cup | 5 |

## Top Current Labels

| Current model label | count |
| --- | ---: |
| Organic | 47 |
| Pen | 31 |
| Iron utensils | 12 |
| Plastic cup | 11 |
| Tin | 11 |
| Paper | 9 |
| Plastic bottle | 8 |
| Unknown object | 7 |
| Plastic bag | 7 |
| Printing industry | 3 |
| Container for household chemicals | 2 |
| Glass bottle | 2 |

## Top Drifts

| Old -> current | count |
| --- | ---: |
| Organic -> Organic | 32 |
| Pen -> Pen | 9 |
| Plastic bag -> Plastic bag | 7 |
| Tin -> Tin | 7 |
| Unknown object -> Pen | 7 |
| Aluminum can -> Pen | 6 |
| Tin -> Pen | 5 |
| Paper -> Organic | 4 |
| Plastic cup -> Plastic cup | 4 |
| Paper -> Plastic cup | 4 |
| Unknown object -> Paper | 3 |
| Printing industry -> Iron utensils | 3 |

## Priority Review Rows

| history_id | priority | old label | current label | conf | exact | route | visual note | queue image |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| 632 | high | Organic | Unknown object | 0.00 | no | no | No clear single object; do not train. | `dataset_v2/low_conf_queue/history_recovery_000632.jpg` |
| 694 | high | Aluminum can | Textile | 0.05 | no | no | Occluded or unclear frame; do not train. | `dataset_v2/low_conf_queue/history_recovery_000694.jpg` |
| 750 | high | Kaggle 3-bin R | Unknown object | 0.00 | no | yes | OBS/no-camera frame; do not train. | `dataset_v2/low_conf_queue/history_recovery_000750.jpg` |
| 753 | high | Kaggle 3-bin R | Unknown object | 0.00 | no | yes | OBS/no-camera frame; do not train. | `dataset_v2/low_conf_queue/history_recovery_000753.jpg` |
| 667 | high | Plastic bottle | Unknown object | 0.00 | no | no | Likely ballpoint pen; bbox/label must be reviewed. | `dataset_v2/low_conf_queue/history_recovery_000667.jpg` |
| 764 | high | Iron utensils | Glass bottle | 0.06 | no | no | Likely metal spoon; current model drifted. | `dataset_v2/low_conf_queue/history_recovery_000764.jpg` |
| 726 | high | Pen | Electronics | 0.05 | no | yes | Likely ballpoint pen; current model drifted. | `dataset_v2/low_conf_queue/history_recovery_000726.jpg` |
| 677 | high | Aluminum can | Glass bottle | 0.07 | no | yes | Likely ballpoint pen; old label was wrong. | `dataset_v2/low_conf_queue/history_recovery_000677.jpg` |
| 759 | high | Plastic bottle | Unknown object | 0.00 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000759.jpg` |
| 719 | high | Unknown object | Tin | 0.05 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000719.jpg` |
| 687 | high | Printing industry | Pen | 0.06 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000687.jpg` |
| 704 | high | Unknown object | Plastic cup | 0.06 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000704.jpg` |
| 743 | high | Glass bottle | Iron utensils | 0.07 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000743.jpg` |
| 702 | high | Tin | Pen | 0.07 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000702.jpg` |
| 747 | high | Kaggle 3-bin I | Plastic cup | 0.07 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000747.jpg` |
| 678 | high | Aluminum can | Pen | 0.07 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000678.jpg` |
| 716 | high | Printing industry | Iron utensils | 0.07 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000716.jpg` |
| 707 | high | Printing industry | Iron utensils | 0.08 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000707.jpg` |
| 705 | high | Tin | Pen | 0.08 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000705.jpg` |
| 684 | high | Tin | Pen | 0.08 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000684.jpg` |
| 689 | high | Aluminum can | Electronics | 0.08 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000689.jpg` |
| 663 | high | Unknown plastic | Plastic bottle | 0.08 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000663.jpg` |
| 679 | high | Paper | Organic | 0.08 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000679.jpg` |
| 711 | high | Tin | Iron utensils | 0.08 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000711.jpg` |
| 763 | high | Plastic bottle | Iron utensils | 0.09 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000763.jpg` |
| 696 | high | Printing industry | Iron utensils | 0.09 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000696.jpg` |
| 748 | high | Glass bottle | Pen | 0.09 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000748.jpg` |
| 774 | high | Plastic bottle | Pen | 0.11 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000774.jpg` |
| 685 | high | Unknown object | Paper | 0.11 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000685.jpg` |
| 723 | high | Aluminum can | Pen | 0.12 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000723.jpg` |
| 692 | high | Aluminum can | Pen | 0.12 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000692.jpg` |
| 698 | high | Tin | Pen | 0.13 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000698.jpg` |
| 742 | high | Kaggle 3-bin I | Organic | 0.13 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000742.jpg` |
| 683 | high | Unknown object | Paper | 0.13 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000683.jpg` |
| 681 | high | Aluminum can | Pen | 0.14 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000681.jpg` |
| 666 | high | Liquid | Paper | 0.15 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000666.jpg` |
| 631 | high | Paper | Iron utensils | 0.16 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000631.jpg` |
| 718 | high | Aluminum can | Pen | 0.19 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000718.jpg` |
| 760 | high | Glass bottle | Organic | 0.24 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000760.jpg` |
| 730 | high | Kaggle 3-bin I | Plastic cup | 0.25 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000730.jpg` |
| 766 | high | Plastic bottle | Organic | 0.25 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000766.jpg` |
| 712 | high | Tin | Pen | 0.26 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000712.jpg` |
| 625 | high | Plastic cup | Organic | 0.28 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000625.jpg` |
| 697 | high | Aluminum can | Pen | 0.32 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000697.jpg` |
| 671 | high | Paper | Organic | 0.42 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000671.jpg` |
| 740 | high | Kaggle 3-bin O | Organic | 0.44 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000740.jpg` |
| 745 | high | Glass bottle | Iron utensils | 0.44 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000745.jpg` |
| 733 | high | Glass bottle | Organic | 0.51 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000733.jpg` |
| 761 | high | Kaggle 3-bin I | Paper | 0.51 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000761.jpg` |
| 769 | high | Plastic bottle | Organic | 0.52 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000769.jpg` |
| 736 | high | Kaggle 3-bin I | Paper | 0.55 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000736.jpg` |
| 744 | high | Kaggle 3-bin R | Paper | 0.55 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000744.jpg` |
| 714 | high | Unknown object | Paper | 0.56 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000714.jpg` |
| 665 | high | Paper | Organic | 0.59 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000665.jpg` |
| 626 | high | Printing industry | Organic | 0.63 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000626.jpg` |
| 621 | high | Paper | Organic | 0.76 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000621.jpg` |
| 737 | high | Kaggle 3-bin I | Plastic bottle | 0.84 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000737.jpg` |
| 771 | high | Kaggle 3-bin I | Plastic bottle | 0.91 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000771.jpg` |
| 741 | high | Glass bottle | Organic | 0.91 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000741.jpg` |
| 770 | high | Ceramic | Organic | 0.97 | no | no |  | `dataset_v2/low_conf_queue/history_recovery_000770.jpg` |

## Suggested Next Pass

1. Review quarantine notes first and mark them no-evidence.
2. Review clear pen/spoon/bottle/leaf examples and correct bbox.
3. Capture new real-camera samples for charger, socket, cable, comb, marker, lighter, plastic bag, eggshell, and batteries.
4. Train specialist only after enough reviewed images exist per label.
