# Model Evaluation V6 Pen Hardware

Date: 2026-06-04

## Dataset Import

Imported three user-downloaded YOLOv8/Roboflow exports from `C:\Users\Admin\Downloads`:

- `PEN.v3i.yolov8.zip` as `roboflow_pen_v3`: 319 images imported.
- `Version2.v1i.yolov8.zip` as `roboflow_version2`: 2857 images imported.
- `cardboard-paper.v1i.yolov8.zip` as `roboflow_cardboard_paper`: 3229 images imported.

Label normalization used preset `pen_hardware_downloads`.

Important exported class counts:

- `Pen`: 2080 boxes.
- `Battery`: 488 boxes.
- `Toothbrush`: 737 boxes.
- `Paper`: 5037 boxes.
- `Cardboard`: 5571 boxes.
- `Organic`: 1918 boxes.
- `Aluminum can`: 5505 boxes.

Export result:

- Images: 20603.
- Boxes: 33448.
- Class count: 45.
- Skipped untrusted queue items: 776.
- Skipped unknown boxes: 0.
- New class IDs: `Pen=42`, `Battery=43`, `Toothbrush=44`.

## Smoke Train

Command:

```powershell
python -m uv run python scripts/train_yolo.py --device 0 --epochs 1 --imgsz 640 --batch 4 --workers 0 --fraction 0.02 --name trash-sorter-v6-pen-hardware-smoke --exist-ok
```

Result:

- Run: `runs/train/trash-sorter-v6-pen-hardware-smoke`.
- Training completed successfully.
- Ultralytics overrode model `nc=42` to `nc=45`.
- Pretrained transfer: `696/708` items.

Smoke metrics are not production-quality because the run used only one epoch and a 2% training fraction. `Pen` validation was present, but recall stayed near zero as expected for a smoke run.

## Promotion Status

Do not replace `models/best.pt` yet.

Current production app model `models/best_candidate_v5.pt` still has 42 classes
and does not contain `Pen`. The smoke model contains `Pen`, `Battery`, and
`Toothbrush`, but it is not promoted.

To avoid a silent camera path before full training, the desktop app now uses a
controlled fallback: if the model sees a low-confidence/new visible object but
cannot classify it, Live/History records `Unknown object` and routes it as
`R -> voco -> bin 2` only when camera dispatch is explicitly armed. The guard
requires Actuation Test Mode, connected UART, enabled valid ROI, detection
inside ROI, stable frames, no active dump, tray-empty re-arm, and the global
cooldown. Suppressed detections remain visible in Live with guard reasons and
must not send UART in a loop.

Next required steps:

1. Capture and annotate local tray-camera samples for `Pen`.
2. Run a full candidate train, for example `trash-sorter-v6-pen-hardware`.
3. Test desktop camera detection with a real pen.
4. Confirm UART is connected and hardware returns ACK for `Pen -> R -> voco`.
5. Promote only after camera and hardware E2E pass.

## 2026-06-05 Manual Pen Re-export

The reviewed manual tray-camera sample `manual_camera_f4afba9b4f5f` was exported
into the YOLO train split as `Pen`.

Re-export result:

- Images: 20604.
- Boxes: 33449.
- Class count: 45.
- `Pen`: 2081 boxes.
- Skipped untrusted queue items: 776.
- Skipped unknown boxes: 0.
- Manual sample label: class `42` (`Pen`).

## 2026-06-05 Resume Train Status

Do not promote any V6 Pen candidate yet.

- Previous candidate `trash-sorter-v6-pen-hardware-b8` reached epoch 8 and has
  weights, but Pen metrics and real camera acceptance are not sufficient for
  production.
- First continuation run
  `trash-sorter-v6-pen-hardware-b8-continue-manual-pen` stopped during epoch 1
  before writing weights; no traceback was present in the log.
- Restarted continuation run
  `trash-sorter-v6-pen-hardware-b8-continue-manual-pen-r2` from
  `runs/train/trash-sorter-v6-pen-hardware-b8/weights/last.pt`.
- Run log:
  `runs/train_logs/trash-sorter-v6-pen-hardware-b8-continue-manual-pen-r2-20260605-171400.log`.
- The r2 run reached train/val cache scan and began epoch `1/100` on CUDA with
  batch `8`, workers `0`, and SGD. It remains a candidate until full metrics and
  real camera/hardware tests pass.

## Hardware Status

CH340/`COM8` is visible and was flashed with the updated firmware on
2026-06-05.

Post-flash serial-level app smoke passed:

- `AUDIO:3 -> ACK:AUDIO:3`, MP3 track 3.
- `AUDIO:4 -> ACK:AUDIO:4`, MP3 track 4.
- `R -> voco\n -> ACK:R`, sort audio `AUDIO:R:4:sort`.
- `I -> taiche\n -> ACK:I`, sort audio `AUDIO:I:3:sort`.

Physical acceptance still requires the operator to confirm that track 3 says
Tai che, track 4 says Vo co, and the servo paths dump into the matching bins.

## 2026-06-06 Guided Capture And Fast Fine-Tune

- Added a 24-frame guided camera session with blur, duplicate, object-size, and
  bbox checks.
- Six frames are split-locked as real holdout data and excluded from immediate
  reference recognition.
- Manual references now use MobileNetV3-Small embeddings with top-5 voting,
  minimum three votes, similarity threshold, and runner-up margin.
- Fast export is fixed to the existing 45 classes and targets at most 4,500
  balanced images.
- Fast training uses 12 frozen epochs at 512px followed by 8 unfrozen epochs at
  640px from the V6 epoch-8 seed.
- Production weights remain unchanged until real-camera and guarded hardware
  acceptance pass.

Verification on 2026-06-06:

- Balanced export: `3,861` images and `6,111` boxes.
- Pen boxes: `2,076` total, split as `1,672 train / 189 valid / 215 test`.
- Reviewed holdout recognition: `Pen`, best similarity `0.8438`, `3/5` votes,
  runner-up margin `0.3073`.
- Stable-query reference lookup falls from about seven seconds on first model
  load/index build to about four milliseconds from cache.
- Empty-tray negative run: `100` live frames, `0` Pen false positives and `0`
  non-empty detections.
- Full checks: `225 passed, 1 skipped`; Ruff, mypy core, and Next.js production
  build passed.
- Fast Stage 1 started on the RTX 3060 as
  `runs/train/trash-sorter-pen-fast-stage1`. It is a candidate only.

Manual COM8 acceptance on 2026-06-06:

- Camera-driven Actuation Test Mode remained off.
- Direct `R` test sent `voco\n` and received `ACK:R` in `3,970ms`.
- No second sort ACK occurred during the following 15 seconds.
- Direct `AUDIO:4` received `ACK:AUDIO:4`; MP3 TX was
  `7E 04 41 00 04 EF`.
- Hardware profile is HOME `D6=90,D7=85`, return settle `1,500ms`, then servo
  idle policy `detach`.

## 2026-06-05 Camera Fallback Hardware Pass

The full Pen model is still not production-ready, but the app no longer waits
for Pen training before acting on a visible pen-like object.

- Runtime model remains `models/best_candidate_v5.pt` with 42 classes.
- `trash-sorter-v6-pen-hardware-b8-continue-manual-pen-r2` is not running and
  has not produced promotable weights beyond the epoch-8 candidate.
- Camera fallback rendered the current pen-like object as `Unknown object`.
- Route used: `Unknown object -> R -> voco\n -> bin 2`.
- Hardware evidence row `724` returned `ACK ok` in `2719ms`.
- Keeping the object visible did not create another hardware row after 20s; the
  guard stayed at `waiting empty tray`.
- Current safe runtime state after verification: camera running, UART connected,
  Actuation Test Mode off.
