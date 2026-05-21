# 7. Frameless main window with custom title bar

Date: 2026-05-21

## Status

Accepted

## Context

Native Windows chrome clashes with the dark dashboard aesthetic. We want corners/colors/buttons under our own QSS.

## Decision

Top-level `MainWindow` is `Qt.FramelessWindowHint`. Custom `TitleBar` widget renders logo + minimize/maximize/close. Drag and double-click toggle handled in `mousePressEvent`/`mouseDoubleClickEvent`.

## Consequences

**Positive:** Visual coherence across light/dark themes. Title bar can host extra status (clock, version) later.
**Negative:** Need to reimplement OS niceties: snap zones, alt-tab focus, multi-monitor edge cases. Some accessibility tools expect native frame.
**Neutral:** Settings can expose a "use native frame" toggle if we discover edge-case OS issues post-release.

## Alternatives considered

- Native frame — rejected for theme inconsistency.
- Borderless + always-on-top — wrong UX, modal feel.

## References

- `app/ui/widgets/title_bar.py`
- `app/ui/main_window.py`
