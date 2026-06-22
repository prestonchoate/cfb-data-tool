# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture tab: live preview + scan + save.

Replaces the original CLI's blind 'S'-hotkey flow with an on-screen Start/Stop,
a live thumbnail of the capture region, a result card, and a Save button. A
"Load Image…" path lets you scan a saved screenshot without the game running
(handy for testing and calibration).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

import cv2

from ..core import capture
from ..core.calibration import resolve_calibration
from ..core.profiles.base import get_profile
from ..core.sound import play_sound
from .hotkey import HotkeyManager
from .widgets.image_view import bgr_to_qpixmap
from .widgets.result_card import ResultCard
from .workers import EngineInitWorker, ScanWorker

logger = logging.getLogger(__name__)


class CaptureTab(QWidget):
    engine_ready = Signal(object)  # emits the Engine once OCR is initialized
    recruit_saved = Signal()       # emits after a scan is saved to the store

    def __init__(self, settings, store, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.store = store
        self.calib = resolve_calibration(
            settings.game_version, settings.profile, settings.monitor_number)
        self.engine = None
        self.frame = None              # current BGR frame (what will be scanned)
        self.last_result = None
        self._scanning = False

        self._build_ui()

        # Live-preview timer (UI thread; a 2400x1440 grab is fast at ~4 fps).
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._tick_preview)

        # Global hotkey -> scan.
        self.hotkey = HotkeyManager(settings.hotkey)
        self.hotkey.triggered.connect(self.scan_now)
        if not self.hotkey.start():
            self._set_status(f"Hotkey '{settings.hotkey}' unavailable — use the Scan button")

        self._init_engine()

    # ---- UI construction -------------------------------------------------
    def _build_ui(self):
        root = QHBoxLayout(self)

        # Left: preview + controls
        left = QVBoxLayout()
        self.preview = QLabel("Preview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(480, 280)
        self.preview.setStyleSheet("background:#111; color:#888; border:1px solid #333;")
        left.addWidget(self.preview, 1)

        controls = QHBoxLayout()
        self.live_btn = QPushButton("▶ Start Live")
        self.live_btn.setCheckable(True)
        self.live_btn.toggled.connect(self._toggle_live)
        self.load_btn = QPushButton("Load Image…")
        self.load_btn.clicked.connect(self._load_image)
        controls.addWidget(self.live_btn)
        controls.addWidget(self.load_btn)
        left.addLayout(controls)

        actions = QHBoxLayout()
        self.scan_btn = QPushButton("⤓ Scan")
        self.scan_btn.clicked.connect(self.scan_now)
        self.scan_btn.setEnabled(False)
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_current)
        self.save_btn.setEnabled(False)
        actions.addWidget(self.scan_btn)
        actions.addWidget(self.save_btn)
        left.addLayout(actions)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#444; padding:2px;")
        left.addWidget(self.status)

        root.addLayout(left, 1)

        # Right: result card (editable, for inline correction)
        self.result_card = ResultCard(
            self.settings.confidence_threshold, get_profile(self.settings.profile))
        self.result_card.changed.connect(lambda: self.save_btn.setEnabled(True))
        root.addWidget(self.result_card, 1)

    def _set_status(self, text: str):
        self.status.setText(text)

    # ---- Engine init -----------------------------------------------------
    def _init_engine(self):
        self._set_status("Initializing OCR engine…")
        self._init_worker = EngineInitWorker(self.settings)
        self._init_worker.ready.connect(self._on_engine_ready)
        self._init_worker.failed.connect(lambda e: self._set_status(f"OCR init failed: {e}"))
        self._init_worker.start()

    def _on_engine_ready(self, engine):
        self.engine = engine
        self.scan_btn.setEnabled(True)
        self._set_status("Ready. Start Live or Load an image, then Scan.")
        self.engine_ready.emit(engine)

    def reload_calibration(self, calib: dict):
        """Apply calibration edited/saved in the Calibrate tab without a restart."""
        self.calib = calib
        if self.engine is not None:
            self.engine.rois = calib["rois"]
        self._set_status("Calibration updated.")

    # ---- Capture / preview ----------------------------------------------
    def _capture_region(self) -> dict:
        return capture.offsets_for_monitor(self.calib["global_offsets"], self.settings.monitor_number)

    def _toggle_live(self, on: bool):
        if on:
            self.live_btn.setText("⏸ Stop Live")
            self._timer.start()
        else:
            self.live_btn.setText("▶ Start Live")
            self._timer.stop()

    def _tick_preview(self):
        try:
            self.frame = capture.grab_region(self._capture_region())
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Capture failed: {exc}")
            self.live_btn.setChecked(False)
            return
        self._show_frame(self.frame)

    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load screenshot", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.load_image_path(path)

    def load_image_path(self, path: str):
        """Load a screenshot from disk (also used by the smoke test)."""
        frame = cv2.imread(path)
        if frame is None:
            self._set_status(f"Could not read image: {path}")
            return
        self.live_btn.setChecked(False)
        self.frame = frame
        self._show_frame(frame)
        self._set_status(f"Loaded {path}")

    def _show_frame(self, frame):
        pix = bgr_to_qpixmap(frame).scaled(
            self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(pix)

    # ---- Scan ------------------------------------------------------------
    def scan_now(self):
        if self.engine is None:
            self._set_status("Engine still initializing…")
            return
        if self.frame is None:
            self._set_status("No frame — Start Live or Load an image first")
            return
        if self._scanning:
            return
        self._scanning = True
        self.scan_btn.setEnabled(False)
        self._set_status("Scanning…")
        self._scan_worker = ScanWorker(self.engine, self.frame.copy())
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.start()

    def _on_scan_done(self, result):
        self._scanning = False
        self.scan_btn.setEnabled(True)
        self.last_result = result
        self.result_card.show_result(result)
        self.save_btn.setEnabled(True)
        self._set_status("Valid scan ✓" if result.valid else "Invalid scan — check highlighted fields")
        self._beep(result.valid)
        if result.valid and self.settings.auto_save_valid:
            self.save_current()

    def _on_scan_failed(self, err: str):
        self._scanning = False
        self.scan_btn.setEnabled(True)
        self._set_status(f"Scan error: {err}")

    def _beep(self, success: bool):
        if not self.settings.use_sounds:
            return
        play_sound(self.settings.success_sound if success else self.settings.fail_sound)

    # ---- Save ------------------------------------------------------------
    def save_current(self):
        if not self.last_result:
            return
        profile = get_profile(self.settings.profile)
        record = self.result_card.edited_record()  # includes any inline corrections
        action = self.store.upsert(profile.to_row(record))
        self.save_btn.setEnabled(False)
        name = record.get("NAME", "recruit")
        self._set_status(f"{action.capitalize()} {name} in the collection.")
        self.recruit_saved.emit()

    # ---- Lifecycle -------------------------------------------------------
    def shutdown(self):
        self._timer.stop()
        self.hotkey.stop()
