# Trash Sorter Pro - Model Evaluation V5

Date: 2026-05-23

## Candidate

- Training run: `runs/train/trash-sorter-v5-low-lr-sgd-continue-to50`
- Candidate model: `models/best_candidate_v5.pt`
- Production model: `models/best.pt`
- Test data: `dataset_v2/yolo_trainset/data.yaml`, split `test`

## Test Metrics

| Model | Precision | Recall | mAP50 | mAP50-95 |
| --- | ---: | ---: | ---: | ---: |
| Production `models/best.pt` | 0.785 | 0.680 | 0.742 | 0.605 |
| Candidate `models/best_candidate_v5.pt` | 0.891 | 0.646 | 0.766 | 0.621 |

## Decision

Candidate is better on precision and mAP, but recall is lower. Keep production unchanged until the candidate passes a real USB camera smoke test.

Recommended next step:

1. Select `models/best_candidate_v5.pt` in Settings.
2. Test with real USB camera on conveyor objects.
3. Verify history captures a labeled image before UART/speaker dispatch.
4. Promote to `models/best.pt` only if camera behavior is stable.

## Weak Classes To Improve

These classes still need more clean data or manual review:

- `Electronics`
- `Iron utensils`
- `Scrap metal`
- `Unknown plastic`
- `Wood`
- classes with very few test samples such as `Ceramic`, `Plastic can`, `Paper cups`
