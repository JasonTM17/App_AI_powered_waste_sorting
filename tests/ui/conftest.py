"""UI test fixtures.

Qt's offscreen platform is forced here so widget tests run headless on
CI / non-GUI hosts without each test file repeating the same boilerplate.
The root ``tests/conftest.py`` also enforces this for safety; this file
makes the UI-scope contract explicit and adds a session-scoped QApplication
so widget construction does not pay the cost of spinning up a new
``QApplication`` per test.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Reuse one ``QApplication`` for the whole test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app  # type: ignore[return-value]
