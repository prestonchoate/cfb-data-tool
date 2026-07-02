# SPDX-License-Identifier: GPL-3.0-or-later
"""Calibration tab: the visual ROI editor + auto-calibration.

Drag/resize the bounding boxes over a screenshot of the recruit card, watch the
coordinates update live, click "Test OCR" to see what each box reads, then Save.
Auto-Calibrate scales the bundled 1440p preset to the user's resolution as a
starting point. This removes the original tool's biggest pain point — hand-editing
pixel offsets in config.py.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ..core import capture
from ..core.calibration import (
    load_preset, resolve_calibration, save_user_calibration, scale_rois,
)
from .widgets.image_view import bgr_to_qpixmap
from .widgets.roi_canvas import RoiCanvas

logger = logging.getLogger(__name__)

_GAME_AREA = "Game capture area"  # name of the single box used in area mode


class CalibrationTab(QWidget):
    saved = Signal(dict)  # emits the new calibration so other tabs can refresh

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.ocr = None
        self.bg_image = None  # BGR ndarray currently shown
        self._updating = False
        self._dirty = False       # unsaved edits since the last save
        self.mode = "card"        # "card" = inner ROIs, "area" = game capture region
        self._area_ref = None     # crop size when area editing began (for ROI scaling)

        self.calib = resolve_calibration(
            settings.game_version, settings.profile, settings.monitor_number)

        self._build_ui()
        self._load_calibration(self.calib)
        self._show_blank_background()

    # ---- UI --------------------------------------------------------------
    def _build_ui(self):
        root = QHBoxLayout(self)

        controls = QVBoxLayout()
        controls.setSpacing(8)

        mode_form = QFormLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Recruit card regions", "Game capture area"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_change)
        mode_form.addRow("Edit:", self.mode_combo)
        self.monitor_spin = QSpinBox()
        try:
            monitor_count = max(1, len(capture.list_monitors()) - 1)
        except Exception:  # noqa: BLE001  (headless / no display)
            monitor_count = 1
        self.monitor_spin.setRange(1, monitor_count)
        self.monitor_spin.setValue(min(self.settings.monitor_number, monitor_count))
        self.monitor_spin.valueChanged.connect(self._on_monitor_change)
        mode_form.addRow("Game monitor:", self.monitor_spin)
        controls.addLayout(mode_form)

        src = QHBoxLayout()
        self.capture_btn = QPushButton("Capture Card")
        self.capture_btn.clicked.connect(self._capture_region)
        self.load_btn = QPushButton("Load Image…")
        self.load_btn.clicked.connect(self._load_image)
        src.addWidget(self.capture_btn)
        src.addWidget(self.load_btn)
        controls.addLayout(src)

        self.res_label = QLabel("")
        self.res_label.setStyleSheet("color:#888;")
        controls.addWidget(self.res_label)

        controls.addWidget(QLabel("Regions:"))
        self.roi_list = QListWidget()
        self.roi_list.currentTextChanged.connect(self._on_list_select)
        controls.addWidget(self.roi_list, 1)

        box = QGroupBox("Selected region (pixels)")
        form = QFormLayout(box)
        self.sp_x = self._spin(); self.sp_y = self._spin()
        self.sp_w = self._spin(); self.sp_h = self._spin()
        form.addRow("X (left):", self.sp_x)
        form.addRow("Y (top):", self.sp_y)
        form.addRow("Width:", self.sp_w)
        form.addRow("Height:", self.sp_h)
        controls.addWidget(box)

        self.test_btn = QPushButton("Test OCR on selected region")
        self.test_btn.clicked.connect(self._test_ocr)
        self.test_btn.setEnabled(False)
        controls.addWidget(self.test_btn)
        self.test_out = QLabel("")
        self.test_out.setWordWrap(True)
        self.test_out.setStyleSheet("background:#111; color:#9cf; padding:6px; border:1px solid #333;")
        self.test_out.setMinimumHeight(48)
        controls.addWidget(self.test_out)

        actions = QHBoxLayout()
        self.save_btn = QPushButton("Save Calibration")
        self.save_btn.clicked.connect(self._save)
        self.reset_btn = QPushButton("Reset to default")
        self.reset_btn.clicked.connect(self._reset)
        actions.addWidget(self.save_btn)
        actions.addWidget(self.reset_btn)
        controls.addLayout(actions)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#2e7d32;")
        controls.addWidget(self.status)

        wrap = QWidget()
        wrap.setLayout(controls)
        wrap.setFixedWidth(300)
        root.addWidget(wrap)

        self.canvas = RoiCanvas()
        self.canvas.roi_changed.connect(self._on_canvas_changed)
        self.canvas.roi_selected.connect(self._on_canvas_selected)
        root.addWidget(self.canvas, 1)

    def _spin(self) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(0, 20000)
        sp.valueChanged.connect(self._on_spin_changed)
        return sp

    def _set_roi_list(self, names):
        self.roi_list.blockSignals(True)
        self.roi_list.clear()
        self.roi_list.addItems(list(names))
        self.roi_list.blockSignals(False)
        if self.roi_list.count():
            self.roi_list.setCurrentRow(0)

    # ---- mode switching --------------------------------------------------
    def _on_mode_change(self, idx: int):
        if idx == 1:
            self._enter_area_mode()
        else:
            self._enter_card_mode()

    def _on_monitor_change(self, value: int):
        self.settings.monitor_number = value
        if self.mode == "area":
            self._enter_area_mode()  # re-grab the newly selected monitor

    def _enter_area_mode(self):
        """Show the full monitor with a single box = the recruit-card capture region."""
        self.mode = "area"
        self.capture_btn.setText("Re-capture Full Monitor")
        self.test_btn.setEnabled(False)
        # These act on the inner card regions, not the capture box.
        self.load_btn.setVisible(False)
        self.reset_btn.setVisible(False)
        go = self.calib["global_offsets"]
        self._area_ref = (go["width"], go["height"])
        if capture.needs_session() and not capture.ensure_session(self.settings.monitor_number):
            QMessageBox.warning(
                self,
                "Screen capture permission required",
                "Monitor capture needs permission to record your screen.\n\n"
                "Approve the desktop portal dialog and select the game monitor, "
                "or load a screenshot instead.",
            )
            frame = np.full((1080, 1920, 3), 30, dtype=np.uint8)
            note = "Live monitor capture unavailable. Load a screenshot or grant portal permission."
        else:
            try:
                frame = capture.grab_region(capture.monitor_region(self.settings.monitor_number))
                note = "Drag the box over the recruit card, then Save. Resize if the card differs."
            except Exception as exc:  # noqa: BLE001
                frame = np.full((1080, 1920, 3), 30, dtype=np.uint8)
                note = f"Full-monitor capture failed ({exc}). Enter the region by hand below."
        self.bg_image = frame
        self.canvas.set_background(bgr_to_qpixmap(frame))
        self.canvas.set_rois({_GAME_AREA: (go["top"], go["height"], go["left"], go["width"])})
        self._set_roi_list([_GAME_AREA])
        self.canvas.select_roi(_GAME_AREA)
        self.status.setText(note)

    def _enter_card_mode(self):
        """Fold any area resize into the inner ROIs, then show the card editor."""
        self._apply_area_scaling()
        self.mode = "card"
        self.capture_btn.setText("Capture Card")
        self.load_btn.setVisible(True)
        self.reset_btn.setVisible(True)
        if self.ocr is not None:
            self.test_btn.setEnabled(True)
        self._load_calibration(self.calib)
        self._show_blank_background()

    def _apply_area_scaling(self):
        """If the capture box was resized, scale inner ROIs to the new crop size."""
        if self.mode != "area" or not self._area_ref:
            return
        go = self.calib["global_offsets"]
        new = (go["width"], go["height"])
        if new != self._area_ref and new[0] > 0 and new[1] > 0:
            self.calib["rois"] = scale_rois(self.calib["rois"], self._area_ref, new)
        self._area_ref = new

    # ---- calibration <-> UI ---------------------------------------------
    def _load_calibration(self, calib: dict):
        self.calib = calib
        w, h = calib["resolution"]
        self.res_label.setText(f"Resolution: {w}×{h}   (source: {calib['source']})")
        self.canvas.set_rois(calib["rois"])
        self.roi_list.blockSignals(True)
        self.roi_list.clear()
        self.roi_list.addItems(list(calib["rois"].keys()))
        self.roi_list.blockSignals(False)
        if self.roi_list.count():
            self.roi_list.setCurrentRow(0)

    def _show_blank_background(self):
        go = self.calib["global_offsets"]
        blank = np.full((go["height"], go["width"], 3), 30, dtype=np.uint8)
        self._set_background(blank, reapply_rois=True)
        self.status.setText("Capture the game region or load a screenshot, then drag the boxes.")

    def _set_background(self, bgr: np.ndarray, reapply_rois: bool):
        self.bg_image = bgr
        rois = self.canvas.get_rois() if (reapply_rois and self.canvas.get_rois()) else self.calib["rois"]
        self.canvas.set_background(bgr_to_qpixmap(bgr))
        self.canvas.set_rois(rois)
        if self.roi_list.currentItem():
            self.canvas.select_roi(self.roi_list.currentItem().text())

    # ---- background sources ---------------------------------------------
    def _capture_region(self):
        if capture.needs_session() and not capture.ensure_session(self.settings.monitor_number):
            QMessageBox.warning(
                self,
                "Screen capture permission required",
                "Monitor capture needs permission to record your screen.\n\n"
                "Approve the desktop portal dialog and select the game monitor.",
            )
            return
        try:
            if self.mode == "area":
                region = capture.monitor_region(self.settings.monitor_number)
            else:
                region = capture.offsets_for_monitor(
                    self.calib["global_offsets"], self.settings.monitor_number)
            frame = capture.grab_region(region)
        except Exception as exc:  # noqa: BLE001
            self.status.setText(f"Capture failed: {exc}")
            return
        self._set_background(frame, reapply_rois=True)
        self.status.setText(
            f"Re-captured monitor {self.settings.monitor_number}. Drag the box over the card, then Save."
            if self.mode == "area"
            else "Captured. Drag/resize boxes, then Test OCR or Save.")

    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load screenshot", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if not path:
            return
        frame = cv2.imread(path)
        if frame is None:
            self.status.setText(f"Could not read {path}")
            return
        self._set_background(frame, reapply_rois=True)
        self.status.setText(f"Loaded {path}")

    # ---- selection + edit sync ------------------------------------------
    def _current_name(self):
        item = self.roi_list.currentItem()
        return item.text() if item else None

    def _on_list_select(self, name: str):
        if not name:
            return
        self.canvas.select_roi(name)
        self._load_spins(name)

    def _on_canvas_selected(self, name: str):
        items = self.roi_list.findItems(name, Qt.MatchExactly)
        if items:
            self.roi_list.blockSignals(True)
            self.roi_list.setCurrentItem(items[0])
            self.roi_list.blockSignals(False)
        self._load_spins(name)

    def _on_canvas_changed(self, name: str, geom):
        self._dirty = True
        if self.mode == "area" and name == _GAME_AREA:
            y, h, x, w = geom
            self.calib["global_offsets"] = {"top": y, "left": x, "width": w, "height": h}
        if name == self._current_name():
            self._load_spins(name)

    def _load_spins(self, name: str):
        geom = self.canvas.get_rois().get(name)
        if not geom:
            return
        y, h, x, w = geom
        self._updating = True
        self.sp_x.setValue(x); self.sp_y.setValue(y)
        self.sp_w.setValue(w); self.sp_h.setValue(h)
        self._updating = False

    def _on_spin_changed(self, _):
        if self._updating:
            return
        name = self._current_name()
        if not name:
            return
        self._dirty = True
        geom = (self.sp_y.value(), self.sp_h.value(), self.sp_x.value(), self.sp_w.value())
        self.canvas.set_roi(name, geom)
        if self.mode == "area" and name == _GAME_AREA:
            y, h, x, w = geom
            self.calib["global_offsets"] = {"top": y, "left": x, "width": w, "height": h}

    # ---- actions ---------------------------------------------------------
    def set_ocr(self, ocr):
        self.ocr = ocr
        self.test_btn.setEnabled(True)

    def _test_ocr(self):
        if self.ocr is None:
            self.test_out.setText("OCR engine still initializing…")
            return
        if self.bg_image is None:
            self.test_out.setText("Capture or load an image first.")
            return
        name = self._current_name()
        if not name:
            return
        y, h, x, w = self.canvas.get_rois()[name]
        crop = self.bg_image[y:y + h, x:x + w]
        if crop.size == 0:
            self.test_out.setText("Region is outside the image.")
            return
        try:
            texts = self.ocr.readtext(crop, detail=0)
        except Exception as exc:  # noqa: BLE001
            self.test_out.setText(f"OCR error: {exc}")
            return
        self.test_out.setText(f"[{name}] " + (" | ".join(texts) if texts else "(no text)"))

    def _reset(self):
        base = load_preset(self.settings.game_version, self.settings.profile)
        target = self.calib["resolution"]
        base_res = tuple(base["base_resolution"])
        rois = base["rois"] if tuple(target) == base_res else scale_rois(base["rois"], base_res, target)
        self.calib = {**self.calib, "rois": rois, "source": "base"}
        self._load_calibration(self.calib)
        self.status.setText("Reset to bundled default (not yet saved).")

    def _save(self):
        if self.mode == "area":
            self._apply_area_scaling()   # fold any capture-box resize into inner ROIs
            rois = self.calib["rois"]
        else:
            rois = self.canvas.get_rois()
        go = self.calib["global_offsets"]
        path = save_user_calibration(
            self.settings.game_version, self.settings.profile,
            self.calib["resolution"], go, rois)
        self.settings.save()  # persist the chosen monitor alongside the calibration
        new_calib = {**self.calib, "rois": rois, "global_offsets": go, "source": "user"}
        self.calib = new_calib
        self._dirty = False
        self.status.setText(f"Saved to {path}")
        self.saved.emit(new_calib)

    def commit_if_dirty(self):
        """Auto-save pending edits (called when leaving the tab or closing the app)
        so the Capture tab always reflects the latest calibration."""
        if self._dirty:
            self._save()
