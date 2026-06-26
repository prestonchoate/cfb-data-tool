# SPDX-License-Identifier: GPL-3.0-or-later
"""Application entry point."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from PySide6.QtGui import QIcon, QPalette, QColor
    from PySide6.QtWidgets import QApplication

    from .ui.main_window import MainWindow

    if sys.platform == "darwin":
        QApplication.setStyle("Fusion")

    app = QApplication(sys.argv)
    app.setApplicationName("CFB Data Tool")
    app.setOrganizationName("cfb-data-tool")

    if sys.platform == "darwin":
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(42, 42, 42))
        palette.setColor(QPalette.WindowText, QColor(208, 208, 208))
        palette.setColor(QPalette.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.AlternateBase, QColor(50, 50, 50))
        palette.setColor(QPalette.Text, QColor(208, 208, 208))
        palette.setColor(QPalette.Button, QColor(55, 55, 55))
        palette.setColor(QPalette.ButtonText, QColor(208, 208, 208))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipBase, QColor(50, 50, 50))
        palette.setColor(QPalette.ToolTipText, QColor(208, 208, 208))
        app.setPalette(palette)

    icon_path = Path(__file__).resolve().parent / "resources" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
