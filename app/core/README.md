# app/core

## Purpose

Pure logic layer — no UI imports. Phase 2 (web) will reuse these modules behind a FastAPI wrapper.

## API surface

- `config.AppConfig` — pydantic schema, `load_config(path)`, `save_config(cfg, path)`.
- `events.{Detection,TrackedDetection,DetectionEvent,AckEvent}` — frozen dataclasses.
- `camera.CameraWorker(source, w, h, mirror)` — QThread, signals: `frame_ready`, `error`, `connected`.
- `inference.InferenceEngine(model_path, device, conf, iou, imgsz, half)` — `predict(frame_bgr) -> list[Detection]`, `update_thresholds(...)`.
- `tracker.Tracker(iou_threshold, max_age)` — `update(detections) -> list[TrackedDetection]`, `should_emit(id)`, `mark_emitted(id)`.
- `uart_protocol.encode_sort/encode_ping/parse_line` — pure functions.
- `uart.UartWorker(port, baud, ack_timeout_ms, auto_reconnect)` — QThread, signals: `ack_received`, `connected`, `error`. Method `send(track_id, command, conf)`.
- `history.HistoryService(db_path)` — `insert/update_ack/query/count_by_class/count_by_hour/export_csv/close`.
- `pipeline.Pipeline(cfg, engine, uart, history_db)` — `process_frame(frame, ts) -> list[Detection]`, `on_ack(...)`, `update_mappings(...)`.

## Env vars

None directly. Config is JSON.

## Run locally

```bash
python -m uv run pytest -q
```

## Test

`tests/unit/` and `tests/integration/`.

## Runbook

- Reset history DB: delete `%APPDATA%/TrashSorter/history.db` (app re-creates).
- Force config defaults: rename `config.json` to `config.json.broken`.
- Diagnose UART: enable `LOG:` lines in firmware; they appear in `app-YYYY-MM-DD.log`.
