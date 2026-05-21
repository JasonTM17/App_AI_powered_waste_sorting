"""Entry point: python -m app."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.widgets.theme import apply_theme
from app.utils.logging import logger, setup_logging


def main() -> int:
    setup_logging()
    logger.info("starting app")
    app = QApplication(sys.argv)
    app.setApplicationName("Trash Sorter Pro")
    app.setOrganizationName("TrashSorter")
    apply_theme(app, "dark")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
