# app/ui

## Purpose

PySide6 UI layer. Imports `app.core` only via public API — no reverse direction.

## API surface

- `main_window.MainWindow(cfg, history)` — frameless shell, sidebar, 5 stacked pages.
- `controller.AppController(cfg, config_path, db_path)` — wires workers to UI; signals: `frame_processed`, `uart_status`, `camera_status`, `model_status`, `snapshot_saved`, `test_camera_result`, `test_uart_result`, `reload_model_result`.
- Widgets: `theme.apply_theme(app, name)`, `TitleBar`, `Sidebar`, `VideoView`, `StatCard`, `Toast`, `Skeleton`, `EmptyState`, `TrayIcon`, `Splash`, `AboutDialog`, `DetectionDetailDialog`.
- Pages: `LivePage`, `HistoryPage`, `MappingPage`, `CapturePage`, `SettingsPage`.

## Env vars

`QT_QPA_PLATFORM=offscreen` for headless testing.

## Run locally

```bash
python -m uv run python -m app
```

## Test

`tests/ui/` — pytest-qt with offscreen platform.

## Runbook

- Theme switch: edit `cfg.theme` and restart (live theme swap will land in v2.1).
- Window stuck off-screen on multi-monitor: edit `config.json` and remove geometry overrides (currently we don't persist geometry — fix planned).
