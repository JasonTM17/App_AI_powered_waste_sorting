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
- Full checks: `226 passed, 1 skipped`; Ruff, mypy core, and Next.js production
  build passed.
- Fast Stage 1 completed on the RTX 3060 as
  `runs/train/trash-sorter-pen-fast-stage1`.
- Fast Stage 2 wrote candidate weights at
  `runs/train/trash-sorter-pen-fast-stage2/weights/best.pt`.
- Stage 2 test evaluation on `dataset_v2/yolo_fast_pen`:
  overall `P=0.627`, `R=0.490`, `mAP50=0.501`, `mAP50-95=0.396`.
- Stage 2 Pen-only test metrics:
  `P=0.640`, `R=0.041`, `mAP50=0.189`, `mAP50-95=0.109`.
- Compared with the existing candidates, Pen-fast is not promotable:
  `models/best.pt` test `mAP50=0.742`, `mAP50-95=0.605`; V5 candidate
  `mAP50=0.766`, `mAP50-95=0.621`.
- Keep runtime on the existing model and use reviewed-reference recognition for
  immediate Pen handling until more real Pen samples and a stronger fine-tune
  pass the acceptance thresholds.

Manual COM8 acceptance on 2026-06-06:

- Camera-driven Actuation Test Mode remained off.
- Direct `R` test sent `voco\n` and received `ACK:R` in `3,970ms`.
- No second sort ACK occurred during the following 15 seconds.
- Direct `AUDIO:4` received `ACK:AUDIO:4`; MP3 TX was
  `7E 04 41 00 04 EF`.
- Hardware profile is HOME `D6=90,D7=85`, return settle `1,500ms`, then servo
  idle policy `detach`.

Runtime recheck on 2026-06-06 after restarting the local agent:

- Agent API is running on `http://127.0.0.1:8765`.
- Runtime model is still the existing non-Pen production path, not the
  Pen-fast candidate.
- PySerial currently sees only Bluetooth ports `COM3` through `COM6`.
- Windows Device Manager has stale/phantom `USB-SERIAL CH340 (COM7/COM8)`
  entries with status `Unknown`, but COM8 is not present to the app.
- The external `USB Camera` entries also have status `Unknown`; the only present
  camera is the integrated webcam, which is intentionally not used for tray
  sorting.
- Because COM8 and the USB tray camera are not present, real camera-to-hardware
  dumping cannot be accepted in this state. Reconnect the CH340 board and the
  external USB camera, then restart/refresh the agent before enabling Actuation
  Test Mode.

## 2026-06-06 Software-Only Common Waste Pass

The next pass is software-only per operator request; hardware acceptance is
deferred.

Implemented:

- Added a curated common-waste catalog for Vietnamese household items such as
  `Vo chuoi`, `Lon nuoc`, `Chai PET`, `Hop giay`, `Khau trang`, `But bi`, and
  `Pin`.
- Added `/api/common-waste/catalog` so web/manual workflows can pick common
  labels while saving canonical classes.
- Data tab now shows quick common-waste choices; selecting a common item fills
  the canonical class used by upload, URL import, camera capture, and guided
  capture.
- Canonical aliases now resolve common ASCII Vietnamese labels such as
  `vo chuoi -> Organic`, `lon nuoc -> Aluminum can`, `chai pet -> Plastic
  bottle`, `but bi -> Pen`, and `khau trang -> Textile`.
- Fast export can include common-waste focus classes and filter tiny/thin boxes.
- Training utility can run with `--no-plots` to avoid plot-time memory failures.

Verification before starting the new candidate:

- Ruff changed-file gate passed.
- `mypy app/core` passed.
- Targeted tests for common catalog, balanced export, and catalog API passed.
- Web production build passed.
- Full pytest after the common-waste changes passed:
  `230 passed, 1 skipped`.
- Manual URL import now requires `source_page_url` and `source_license` so web
  images cannot enter the dataset without source-rights metadata.

New software trainset:

- Export: `dataset_v2/yolo_fast_common`.
- Images/boxes: `5,981` images / `10,200` boxes.
- Splits: `4,817 train / 554 valid / 610 test`.
- Quality filter: `min_box_area=0.001`, `min_box_side=0.005`, skipped `31`
  small boxes.
- Strong common classes include `Cardboard=2,080`, `Aluminum can=1,852`,
  `Paper=1,665`, `Plastic bottle=1,021`, `Plastic bag=748`, `Organic=685`,
  and `Pen=722`.
- Weak common classes still need more reviewed real/web samples:
  `Tetra pack=20`, `Textile=23`, `Disposable tableware=6`, `Ceramic=2`.

Candidate training started:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_common_software_training.ps1
```

Run:

- `runs/train/trash-sorter-common-software-stage1`.
- Seed: `runs/train/trash-sorter-v6-pen-hardware-b8/weights/best.pt`.
- Settings: 30 epochs, 640px, batch 8, disk cache, AMP, cosine LR,
  `close_mosaic=5`, `lr0=0.002`, plots disabled.
- Candidate only; do not promote without test metrics and real-camera checks.
- Early training signal: epoch 1 validation `mAP50=0.474`, `mAP50-95=0.375`;
  epoch 2 validation `mAP50=0.521`, `mAP50-95=0.414`. Training remains in
  progress.

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
