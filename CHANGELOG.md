# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · SemVer.

## [Unreleased]

- TBD next milestone improvements.

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
- CI workflow: ruff + mypy advisory, pytest with 65% core coverage gate.

### Notes
- Spec: `docs/superpowers/specs/2026-05-21-trash-sorter-desktop-v2-design.md` (untracked, private).
