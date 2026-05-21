# 2. PySide6 over PyQt5

Date: 2026-05-21

## Status

Accepted

## Context

We need a Python desktop GUI framework. Choices: PyQt5/6 (Riverbank, GPL/commercial), PySide6 (Qt Group, LGPL), Tkinter (stdlib), Kivy, Toga. The app ships as a closed Windows binary; license fit matters.

## Decision

Use PySide6 (Qt 6.7+).

## Consequences

**Positive:** Modern Qt 6, official Qt Group support, LGPL allows closed-source distribution without per-seat fees, large widget set, pyqtgraph compatible, qtawesome icons available.
**Negative:** Larger install (~150 MB), some PyQt5 examples don't translate 1:1.
**Neutral:** API differences from PyQt5 minor (Signal vs pyqtSignal, Property vs pyqtProperty).

## Alternatives considered

- PyQt5 — rejected: GPL forces source disclosure or paid commercial license.
- Tkinter — rejected: dated look, hard to theme to spec.
- Kivy — rejected: better for touch/mobile, weaker desktop ergonomics.

## References

- https://doc.qt.io/qtforpython-6/
- https://www.qt.io/licensing/
