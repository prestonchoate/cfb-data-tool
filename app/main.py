# SPDX-License-Identifier: GPL-3.0-or-later
"""Application entry point."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .platform.ui_theme import apply_platform_theme
    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("CFB Data Tool")
    app.setOrganizationName("cfb-data-tool")
    apply_platform_theme(app)

    icon_path = Path(__file__).resolve().parent / "resources" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
