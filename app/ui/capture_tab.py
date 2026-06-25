# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture tab: live preview + scan + save.

Replaces the original CLI's blind 'S'-hotkey flow with an on-screen Start/Stop,
a live thumbnail of the capture region, a result card, and a Save button. A
"Load Image…" path lets you scan a saved screenshot without the game running
(handy for testing and calibration).
"""

from __future__ import annotations

import copy
import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QVBoxLayout, QWidget,
)

import cv2
import numpy as np

from ..core import capture
from ..core.calibration import resolve_calibration
from ..core.profiles.base import get_profile
from ..core.sound import play_sound
from .hotkey import HotkeyManager
from .widgets.image_view import bgr_to_qpixmap
from .widgets.result_card import ResultCard
from .workers import EngineInitWorker, ScanWorker

logger = logging.getLogger(__name__)

# Auto-capture frame-diff thresholds (mean abs grayscale diff on the name ROI).
# Tunable — depends on the card's transition animation.
_AUTO_STABLE_DIFF = 2.5   # below this between ticks, the card has settled
_AUTO_NEW_DIFF = 6.0      # above this vs the last capture, it's a different recruit


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
        self._scan_is_auto = False

        # Auto-capture + review queue state
        self.auto_capture = False
        self._queue: list[dict] = []        # records awaiting review
        self._active_queue_row = None       # queue row currently shown in the card
        self._prev_name_roi = None          # previous tick's name ROI (grayscale)
        self._last_scan_name_roi = None     # name ROI of the last auto-captured card

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
        self.scan_btn.clicked.connect(lambda: self.scan_now())
        self.scan_btn.setEnabled(False)
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_current)
        self.save_btn.setEnabled(False)
        actions.addWidget(self.scan_btn)
        actions.addWidget(self.save_btn)
        left.addLayout(actions)

        self.auto_check = QCheckBox("Auto-capture new recruits")
        self.auto_check.setToolTip(
            "While Live is running, detect each new recruit card and scan it into "
            "the review queue automatically.")
        self.auto_check.toggled.connect(self._toggle_auto)
        left.addWidget(self.auto_check)

        # Review queue (only shown in auto-capture mode)
        self.queue_group = QGroupBox("Review queue")
        qlay = QVBoxLayout(self.queue_group)
        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(150)
        self.queue_list.currentRowChanged.connect(self._on_queue_select)
        qlay.addWidget(self.queue_list)
        qbtns = QHBoxLayout()
        self.save_all_btn = QPushButton("Save All to Collection")
        self.save_all_btn.clicked.connect(self._save_all)
        self.save_all_btn.setEnabled(False)
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setToolTip("Discard the highlighted recruit from the queue (e.g. a duplicate).")
        self.remove_btn.clicked.connect(self._remove_selected)
        self.remove_btn.setEnabled(False)
        self.clear_queue_btn = QPushButton("Clear")
        self.clear_queue_btn.clicked.connect(self._clear_queue)
        qbtns.addWidget(self.save_all_btn)
        qbtns.addWidget(self.remove_btn)
        qbtns.addWidget(self.clear_queue_btn)
        qlay.addLayout(qbtns)
        self.queue_group.setVisible(False)
        left.addWidget(self.queue_group)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#444; padding:2px;")
        left.addWidget(self.status)

        root.addLayout(left, 1)

        # Right: result card (editable, for inline correction)
        self.result_card = ResultCard(
            self.settings.confidence_threshold, get_profile(self.settings.profile))
        self.result_card.changed.connect(self._on_card_changed)
        root.addWidget(self.result_card, 1)

    def _set_status(self, text: str):
        self.status.setText(text)

    # ---- Engine init -----------------------------------------------------
    def _init_engine(self):
        self._set_status("Initializing OCR engine…")
        # Create the OCR backend on the main thread — onnxruntime deadlocks
        # when initialized from a background thread on macOS.
        from ..core.ocr.rapidocr_engine import RapidOcrEngine
        try:
            ocr = RapidOcrEngine()
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"OCR init failed: {exc}")
            return
        self._init_worker = EngineInitWorker(self.settings, ocr=ocr)
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
            self.engine.scale = calib.get("cv_scale", 1.0)
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
        if self.auto_capture and self.engine is not None and not self._scanning:
            self._check_auto_capture()

    # ---- Auto-capture ----------------------------------------------------
    def _toggle_auto(self, on: bool):
        self.auto_capture = on
        self.queue_group.setVisible(on)
        self._prev_name_roi = None
        self._last_scan_name_roi = None
        if on and not self.live_btn.isChecked():
            self.live_btn.setChecked(True)  # auto-capture needs the live feed
        self._set_status("Auto-capture ON — new recruits are queued for review."
                         if on else "Auto-capture off.")

    def _check_auto_capture(self):
        roi = self.calib["rois"].get("name")
        if roi is None:
            return
        name_roi = self._gray_crop(self.frame, roi)
        if name_roi is None:
            return
        prev, self._prev_name_roi = self._prev_name_roi, name_roi
        if prev is None:
            return  # need a previous frame to judge stability
        stable = self._roi_diff(name_roi, prev) < _AUTO_STABLE_DIFF
        is_new = (self._last_scan_name_roi is None
                  or self._roi_diff(name_roi, self._last_scan_name_roi) > _AUTO_NEW_DIFF)
        if stable and is_new:
            self._last_scan_name_roi = name_roi
            self.scan_now(auto=True)

    @staticmethod
    def _gray_crop(frame, roi):
        y, h, x, w = roi
        crop = frame[y:y + h, x:x + w]
        if crop.size == 0:
            return None
        return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _roi_diff(a, b) -> float:
        if a.shape != b.shape:
            return 255.0
        return float(np.mean(cv2.absdiff(a, b)))

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
    def scan_now(self, auto: bool = False):
        if self.engine is None:
            if not auto:
                self._set_status("Engine still initializing…")
            return
        if self.frame is None:
            if not auto:
                self._set_status("No frame — Start Live or Load an image first")
            return
        if self._scanning:
            return
        self._scanning = True
        self._scan_is_auto = auto
        self.scan_btn.setEnabled(False)
        self._set_status("Auto-capturing…" if auto else "Scanning…")
        self._scan_worker = ScanWorker(self.engine, self.frame.copy())
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.start()

    def _on_scan_done(self, result):
        self._scanning = False
        self.scan_btn.setEnabled(True)
        self._beep(result.valid)
        if self._scan_is_auto:
            self._enqueue(result)
            return
        self.last_result = result
        self._active_queue_row = None
        self.result_card.show_result(result)
        self.save_btn.setEnabled(True)
        self._set_status("Valid scan ✓" if result.valid else "Invalid scan — check highlighted fields")
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

    # ---- Review queue ----------------------------------------------------
    def _on_card_changed(self):
        self.save_btn.setEnabled(True)
        # Keep the selected queue entry in sync with inline edits.
        if self._active_queue_row is not None and self._active_queue_row < len(self._queue):
            self._queue[self._active_queue_row] = self.result_card.edited_record()
            self._refresh_queue_item(self._active_queue_row)

    def _queue_label(self, record: dict) -> str:
        valid, _ = get_profile(self.settings.profile).validate(record)
        mark = "✓" if valid else "✗"
        return (f"{mark} {record.get('NAME', '?')} — {record.get('POSITION', '?')} "
                f"— ⭐{record.get('STARS', '?')}")

    def _enqueue(self, result):
        self._queue.append(copy.deepcopy(result.record))
        self.queue_list.addItem(self._queue_label(self._queue[-1]))
        self._update_queue_buttons()
        self.queue_list.setCurrentRow(len(self._queue) - 1)  # shows it in the card
        self._set_status(f"Queued {result.record.get('NAME', 'recruit')} — "
                         f"{len(self._queue)} awaiting review.")

    def _refresh_queue_item(self, row: int):
        item = self.queue_list.item(row)
        if item:
            item.setText(self._queue_label(self._queue[row]))

    def _on_queue_select(self, row: int):
        if row is None or row < 0 or row >= len(self._queue):
            self._active_queue_row = None
            return
        self._active_queue_row = row
        self.result_card.show_record(self._queue[row])
        self.save_btn.setEnabled(True)

    def _remove_queue_row(self, row: int):
        del self._queue[row]
        self.queue_list.takeItem(row)
        self._active_queue_row = None
        self._update_queue_buttons()

    def _remove_selected(self):
        row = self.queue_list.currentRow()
        if 0 <= row < len(self._queue):
            self._remove_queue_row(row)

    def _update_queue_buttons(self):
        has = bool(self._queue)
        self.save_all_btn.setEnabled(has)
        self.remove_btn.setEnabled(has)

    def _save_all(self):
        if not self._queue:
            return
        profile = get_profile(self.settings.profile)
        saved = skipped = 0
        for record in self._queue:
            if profile.validate(record)[0]:
                self.store.upsert(profile.to_row(record))
                saved += 1
            else:
                skipped += 1
        self._clear_queue()
        self.recruit_saved.emit()
        msg = f"Saved {saved} recruit(s) to the collection."
        if skipped:
            msg += f" Skipped {skipped} invalid (fix them and re-scan)."
        self._set_status(msg)

    def _clear_queue(self):
        self._queue.clear()
        self.queue_list.clear()
        self._active_queue_row = None
        self._update_queue_buttons()

    # ---- Save ------------------------------------------------------------
    def save_current(self):
        record = self.result_card.edited_record()  # includes any inline corrections
        if record is None:
            return
        profile = get_profile(self.settings.profile)
        action = self.store.upsert(profile.to_row(record))
        self.save_btn.setEnabled(False)
        name = record.get("NAME", "recruit")
        # If this record came from the review queue, drop it now that it's saved.
        if self._active_queue_row is not None and self._active_queue_row < len(self._queue):
            self._remove_queue_row(self._active_queue_row)
        self._set_status(f"{action.capitalize()} {name} in the collection.")
        self.recruit_saved.emit()

    # ---- Lifecycle -------------------------------------------------------
    def shutdown(self):
        self._timer.stop()
        self.hotkey.stop()
