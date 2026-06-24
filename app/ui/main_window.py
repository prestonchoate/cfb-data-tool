# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: tabbed shell — Capture, Calibrate, Data, Settings."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from ..config.settings_store import Settings
from ..core import profiles  # noqa: F401  (registers built-in profiles)
from ..core.profiles.base import get_profile
from ..io.store import RecordStore
from .calibration_tab import CalibrationTab
from .capture_tab import CaptureTab
from .data_tab import DataTab
from .settings_tab import SettingsTab
from .update_checker import UpdateCheckWorker


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings | None = None):
        super().__init__()
        self.settings = settings or Settings.load()
        self.setWindowTitle("CFB Data Tool")
        self.resize(1100, 680)

        self.store = RecordStore(self.settings.sqlite_path, get_profile(self.settings.profile))

        # -- update banner (hidden until an update is found) --
        self._update_banner = QWidget()
        self._update_banner.setStyleSheet(
            "background:#1a6dd4; color:white; padding:6px; font-size:13px;"
        )
        banner_layout = QHBoxLayout(self._update_banner)
        banner_layout.setContentsMargins(12, 4, 12, 4)
        self._update_label = QLabel()
        self._update_label.setStyleSheet("color:white;")
        banner_layout.addWidget(self._update_label, 1)
        download_btn = QPushButton("Download")
        download_btn.setStyleSheet("color:white; font-weight:bold; border:1px solid white; padding:3px 10px;")
        download_btn.setCursor(Qt.PointingHandCursor)
        download_btn.clicked.connect(self._open_release)
        banner_layout.addWidget(download_btn)
        dismiss_btn = QPushButton("✕")
        dismiss_btn.setFixedWidth(28)
        dismiss_btn.setStyleSheet("color:white; font-weight:bold; border:none;")
        dismiss_btn.setCursor(Qt.PointingHandCursor)
        dismiss_btn.clicked.connect(self._update_banner.hide)
        banner_layout.addWidget(dismiss_btn)
        self._update_banner.hide()
        self._release_url = ""

        # -- tabs --
        tabs = QTabWidget()
        self.capture_tab = CaptureTab(self.settings, self.store)
        self.calibration_tab = CalibrationTab(self.settings)
        self.data_tab = DataTab(self.settings, self.store)
        tabs.addTab(self.capture_tab, "Capture")
        tabs.addTab(self.calibration_tab, "Calibrate")
        tabs.addTab(self.data_tab, "Data")
        tabs.addTab(SettingsTab(self.settings), "Settings")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._update_banner)
        layout.addWidget(tabs, 1)
        self.setCentralWidget(central)

        # New scans land in the store -> reflect them in the Data tab.
        self.capture_tab.recruit_saved.connect(self.data_tab.refresh)

        # Auto-commit calibration edits when leaving the Calibrate tab; refresh the
        # Data tab when entering it.
        self._tabs = tabs
        self._calib_index = tabs.indexOf(self.calibration_tab)
        self._data_index = tabs.indexOf(self.data_tab)
        self._prev_index = tabs.currentIndex()
        tabs.currentChanged.connect(self._on_tab_changed)

        # Share the OCR engine with the calibration tab's "Test OCR" once ready,
        # and refresh capture's ROIs live when a calibration is saved.
        self.capture_tab.engine_ready.connect(
            lambda engine: self.calibration_tab.set_ocr(engine.ocr))
        if self.capture_tab.engine is not None:
            self.calibration_tab.set_ocr(self.capture_tab.engine.ocr)
        self.calibration_tab.saved.connect(self.capture_tab.reload_calibration)

        # Check for updates in the background.
        self._update_worker = UpdateCheckWorker(self)
        self._update_worker.update_available.connect(self._show_update_banner)
        self._update_worker.start()

    def _show_update_banner(self, version: str, url: str):
        self._release_url = url
        self._update_label.setText(f"A new version is available: v{version}")
        self._update_banner.show()

    def _open_release(self):
        if self._release_url:
            QDesktopServices.openUrl(self._release_url)

    def _on_tab_changed(self, index):
        if self._prev_index == self._calib_index:
            self.calibration_tab.commit_if_dirty()
        if index == self._data_index:
            self.data_tab.refresh()
        self._prev_index = index

    def closeEvent(self, event):
        self.calibration_tab.commit_if_dirty()
        self.capture_tab.shutdown()
        self.store.close()
        super().closeEvent(event)
