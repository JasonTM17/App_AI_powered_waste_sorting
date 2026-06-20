# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · SemVer.

## [Unreleased]

## [2.2.0] – 2026-06-21

### Added
- Cloud-persistent Eco-Share posts, likes, reposts, and comment threads.
- Private account avatar upload with signed Supabase Storage URLs.
- Separate Admin Settings, Model, Audio, and Logs experiences through the protected hardware bridge.

### Fixed
- Corrected AI confidence display from percentage double-scaling.
- Notification actions now navigate in-app to the assigned bin map instead of reloading the login session.
- Added password visibility controls and account-chip navigation.
## [2.1.1] – 2026-06-20

### Added
- Authenticated Admin realtime event cursor and map refresh for bin fullness,
  alerts, devices, and reports.

### Fixed
- Admin and User dashboards now receive the same hardware fullness changes
  without requiring a manual map refresh.

## [2.1.0] – 2026-06-20

### Added
- Production cloud map, scoped realtime bin fullness, collection alerts, and the
  Admin-only hardware bridge for camera/live operations.
- DeepSeek-backed EcoPet chat with Vietnamese quality safeguards, role-scoped
  context, User monthly quota, and a safe Vietnamese fallback.
- A persistent hardware-sensor assignment on the map: Admin maps one physical
  `BIN:1`, `BIN:2`, or `BIN:3` sensor reading to one cloud bin; Users can view
  the live result but cannot change the shared hardware mapping.
- Detailed operator guide for the map-to-hardware sensor flow and release notes.

### Changed
- Map sensor controls now explain their purpose, state that they never reset a
  fullness percentage, and keep the action on a separate row to avoid overlap.
- The persisted sensor assignment is reloaded after a page refresh, so the map
  continues to show the bin currently receiving hardware data.

### Fixed
- Removed the misleading generic “Chọn” map control and restored a visible
  success message on the User map.
- Hardened bridge restart/reconnection and reduced the demo-target database
  write to one scoped upsert.

### Fixed
- Stabilized Live labels and servo dispatch by tracking route consensus across
  class-name changes for the same physical object.
- Restricted reviewed-image corrections to explicit confusion pairs and disabled
  unsafe exact-name promotion for generic unknown objects by default.
- Raised legacy bottle, pen, and three-bin confidence gates to reduce empty-tray
  and cross-class false positives.
- Open USB cameras with MJPG before requesting 1280x720 and log the actual capture
  resolution for hardware diagnosis.
- Route metal utensils to the inorganic bin instead of the recyclable bin.

## [2.0.0] – 2026-05-21

First release of the rewritten Trash Sorter Desktop. Replaces the original
PyInstaller-bundled binary with a modular PySide6 codebase, modern dark UI, and
testable core split from UI.

### Added
- Modular core (`app/core/`): camera, inference, tracker, uart_protocol, uart, history, pipeline.
- 5-tab UI (Live, Lịch sử, Mapping, Capture, Cài đặt).
- Frameless dark/light theme, custom title bar, system tray.
- SQLite history with bar+area charts via pyqtgraph.
- Atomic config save with corrupt-recovery.
- Hot-reload model.
- Snapshot to `%APPDATA%/TrashSorter/snapshots/`.
- Auto-capture low-confidence frames + YOLO format export.
- ADRs for major decisions (`docs/adr/`).
- `config.example.json` mapping all 42 model classes (from upstream Roboflow dataset) into 6 physical bins.
- CI workflow: ruff + mypy advisory, pytest with 65% core coverage gate.

### Notes
- Spec: `docs/superpowers/specs/2026-05-21-trash-sorter-desktop-v2-design.md` (untracked, private).
