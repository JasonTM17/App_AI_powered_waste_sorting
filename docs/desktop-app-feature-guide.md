# Desktop app feature guide

The desktop app is the main hardware operator interface for Trash Sorter Pro. It
runs as a Windows PySide6 EXE and controls real local resources: USB camera,
YOLO runtime, local history DB, laptop/hardware speaker, and UART/Arduino.

Docker Hub stores the verified EXE bundle as an artifact image. The PySide GUI
is not intended to run inside Linux containers.

## Runtime responsibilities

| Area | Desktop owns | Cloud/web owns |
| --- | --- | --- |
| Camera | USB camera selection, start/stop, ROI, frame quality, preview. | Remote monitoring through agent/bridge only. |
| Inference | YOLO model load, specialist model, thresholds, post-corrections. | Model status display and admin controls. |
| Dispatch | Guarded route decision, bin mapping, UART command, ACK state. | Observability and config surface. |
| Audio | Laptop PowerShell MediaPlayer playback or hardware speaker mode. | Audio settings UI, voice-pack status, test trigger. |
| History | Local SQLite insert/update/export and image references. | Cloud sync/read via bridge. |
| Training | Manual capture/review/export/train scripts. | Admin training UI and reporting. |

## Screenshots

| Live Detection | Mapping |
| --- | --- |
| ![Desktop live detection](assets/screenshots/desktop-live-detection.png) | ![Desktop mapping](assets/screenshots/desktop-mapping.png) |

| Training | Settings |
| --- | --- |
| ![Desktop training](assets/screenshots/desktop-training.png) | ![Desktop settings](assets/screenshots/desktop-settings.png) |

## Hardware prototype media

| Prototype overview | Organic bin | Inorganic bin and controller |
| --- | --- | --- |
| [![Prototype overview](assets/demo/photos/trash-sorter-prototype-overview.jpg)](assets/demo/photos/trash-sorter-prototype-overview.jpg) | [![Organic bin](assets/demo/photos/organic-bin-prototype.jpg)](assets/demo/photos/organic-bin-prototype.jpg) | [![Inorganic bin and controller](assets/demo/photos/inorganic-bin-controller.jpg)](assets/demo/photos/inorganic-bin-controller.jpg) |

Demo videos:

- [Product overview](assets/demo/product-demo-overview.mp4)
- [Hardware front view](assets/demo/hardware-front-view.mp4)
- [Organic bin demo](assets/demo/organic-bin-demo.mp4)
- [Inorganic bin demo](assets/demo/inorganic-bin-demo.mp4)

## Main desktop pages

### Live

Live mode shows the camera feed, detection overlay, current class, route, and
dispatch state. It is intentionally conservative:

- camera starts only after model loading is ready;
- camera can fall back to a shared camera stream when another runtime owns the
  physical camera lock;
- auto sorting can be disabled independently from live preview;
- multiple-class frames are blocked from dispatch and can trigger warning audio;
- empty-tray re-arm prevents repeated dispatch for the same object;
- ROI, stable-frame, cooldown, busy/settle, and camera quality guards all run
  before UART is allowed.

### History

History is written locally first. Rows contain timestamp, track id, class id/name,
confidence, bbox, route label, bin index, UART command, ACK status, RTT, owner
username when available, and optional image paths.

Operator tasks:

- inspect recent recognitions;
- export CSV;
- review labels when a class is disputed;
- backfill owner username before cloud sync;
- use history evidence for model retraining.

### Mapping

Mapping connects detailed YOLO classes to three operational bins:

| Code | Bin | Typical content |
| --- | --- | --- |
| `O` | Hữu cơ | Organic, banana peel, eggshell, leftover food, wood, liquid. |
| `R` | Vô cơ | Ceramic, textile, disposable tableware, cigarette, other non-recyclable waste. |
| `I` | Tái chế | Plastic bottle, paper, cardboard, glass bottle, aluminum can, metal. |

Mapping changes affect real dispatch. Keep changes deliberate and test with
camera disabled or test mode before enabling automatic sorting.

### Training/data

The training page helps collect and review low-confidence samples. The safe
promotion flow is:

1. capture uncertain objects from the real camera;
2. review labels and boxes;
3. mark trusted trainable samples;
4. export YOLO train/valid/test split;
5. train a candidate model under `runs/train/...`;
6. evaluate on holdout data;
7. run camera/hardware acceptance;
8. promote model intentionally.

The app must not silently promote unreviewed queue samples into production.

### Settings

Settings cover:

- camera source, resolution, mirror, rotation, ROI;
- model path, confidence, IoU, image size, device;
- specialist model config;
- UART port, baud, ACK timeout, auto reconnect;
- speaker output mode, voice gender, cooldown;
- dispatch guard thresholds;
- web launcher behavior.

Changing camera/model settings can restart worker threads. The controller keeps
worker lifetimes explicit so UI does not freeze during normal changes.

## Laptop speaker and hardware speaker

The app supports two output modes:

| Mode | Path | Behavior |
| --- | --- | --- |
| Laptop speaker | Windows PowerShell + WPF `MediaPlayer` for bundled voice files. | Used for local voice pack playback and laptop audio test. |
| Hardware speaker | UART audio commands to the Arduino/DFPlayer-style module. | Used when speaker output mode is hardware. |

Important separation:

- laptop mode must not send hardware speaker test audio;
- hardware mode must not play laptop audio for sort dispatch;
- proximity/full-bin sensor audio mode is synced to UART so the microcontroller
  knows whether it should play hardware alerts;
- test audio runs outside the UI thread and emits one final success/failure.

## Camera and no-hardware behavior

The desktop app should be safe on a laptop with no connected machine:

- app opens without camera and UART;
- camera start fails with a clear operator message when no USB camera is found;
- UART disabled/offline state blocks automatic dispatch;
- web launcher can open production cloud without starting local hardware;
- setting `TRASH_SORTER_DISABLE_UART_AUTO_SELECT=1` prevents automatic UART port
  selection in container/headless contexts.

## Release EXE artifact

Build:

```powershell
python -m uv run python scripts/build_exe.py
```

Expected artifact:

```text
dist/TrashSorterPro/TrashSorterPro.exe
```

The Docker Hub desktop image is an artifact image:

```text
nguyenson1710/trash-sorter-desktop-exe:<git-sha>
```

It contains the verified `dist/TrashSorterPro/` folder plus checksums and
metadata. It is not a runnable Linux GUI container.

## Manual release checklist

- Open EXE on Windows.
- Confirm UI does not freeze on startup.
- Start with no camera connected and verify safe failure.
- Start with camera connected and verify live preview.
- Test male and female laptop speaker audio.
- Switch laptop/hardware speaker modes and verify the wrong path is not used.
- Check UART disabled/offline status blocks automatic dispatch.
- Connect Arduino/ESP32 and run one guarded test dispatch if hardware is
  available.
- Verify history row insert/update and ACK status.
- Open web dashboard launcher and confirm it does not freeze desktop.
