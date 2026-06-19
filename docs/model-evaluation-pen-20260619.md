# Pen Candidate Evaluation - 2026-06-19

## Candidate

- Runtime path: `models/learn-now-pen-20260619-candidate.pt`
- Training source: `dataset_v2/yolo_learn_now_micro`
- Stage 2 run: `runs/train/learn-now-micro-pen-20260619-175356-stage2`
- SHA-256: `FCA4B6852A3E7ED3429F7BC831C282E93B1CC54D62BBC9E418B5D23BED4BD9D3`

## Holdout Results

The candidate was evaluated on the micro dataset test split without overlap between train, validation, and test hashes.

| Metric | Candidate | Previous runtime model |
| --- | ---: | ---: |
| Overall precision | 0.721 | 0.396 |
| Overall recall | 0.227 | 0.176 |
| Overall mAP50 | 0.296 | 0.165 |
| Overall mAP50-95 | 0.252 | 0.131 |
| Pen precision | 1.000 | 0.555 |
| Pen recall | 0.886 | 1.000 |
| Pen mAP50 | 0.995 | 0.995 |
| Pen mAP50-95 | 0.837 | 0.760 |

## Runtime Safety

- A detection covering more than 82% of the frame cannot dispatch.
- A detection crop with Laplacian sharpness below 24 cannot dispatch.
- Blocked detections are not written to history and do not trigger speaker or UART output.
- Automatic actuation stays disabled for the supervised desktop smoke test.

The current USB camera does not expose software autofocus. Physical focus, camera distance, lighting, and keeping one complete object inside the tray remain required for reliable recognition.
