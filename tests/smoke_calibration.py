# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless smoke test for the Phase 3 calibration tab.

Exercises: load a screenshot -> ROIs present -> shared OCR ready -> Test OCR reads
the name box -> edit an ROI -> Save -> user-override persists and round-trips ->
Capture tab picks up the new calibration.

    python tests/smoke_calibration.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402

import app.core.calibration as cal  # noqa: E402
import app.config.settings_store as ss  # noqa: E402

# Isolate user-preset + settings writes and force the base 1440p resolution so
# the bundled ROIs line up with the 2400x1440 fixture crop.
_tmp = Path(tempfile.mkdtemp())
cal.USER_PRESETS_DIR = _tmp / "presets"
cal.detect_resolution = lambda *a, **k: (2560, 1440)
ss.CONFIG_DIR = _tmp
ss.SETTINGS_PATH = _tmp / "settings.json"

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.config.settings_store import Settings  # noqa: E402
from app.core.calibration import load_user_calibration, resolve_calibration  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def _fixture():
    root = Path(__file__).resolve().parent / "fixtures" / "screenshots"
    for p in sorted(root.rglob("*.png")):
        return str(p)
    return None


def _wait(app, pred, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if pred():
            return True
        time.sleep(0.05)
    return False


def main() -> int:
    fixture = _fixture()
    if not fixture:
        print("FAIL: no fixtures")
        return 1

    app = QApplication.instance() or QApplication(sys.argv)
    settings = Settings()
    settings.use_sounds = False
    settings.sqlite_path = str(_tmp / "data.db")
    window = MainWindow(settings)
    window.show()
    ctab = window.calibration_tab

    # ROIs loaded from the base preset
    rois = ctab.canvas.get_rois()
    assert "name" in rois and len(rois) >= 10, f"ROIs not loaded: {list(rois)}"
    print(f"• {len(rois)} ROIs loaded; resolution={ctab.calib['resolution']} source={ctab.calib['source']}")

    # Background = fixture
    ctab._set_background(cv2.imread(fixture), reapply_rois=True)
    assert ctab.bg_image is not None
    print(f"• loaded background: {Path(fixture).name}")

    # Shared OCR becomes ready via the capture tab's engine init
    print("• waiting for shared OCR engine…")
    if not _wait(app, lambda: ctab.ocr is not None, timeout=120):
        print("FAIL: OCR never shared to calibration tab")
        return 1

    # Test OCR on the name box
    ctab.roi_list.setCurrentItem(ctab.roi_list.findItems("name", __import__("PySide6").QtCore.Qt.MatchExactly)[0])
    ctab._test_ocr()
    out = ctab.test_out.text()
    print(f"• Test OCR [name] -> {out!r}")
    assert "no text" not in out and len(out) > 8, "Test OCR returned nothing"

    # Edit the position ROI and save
    edited = (22, 118, 1402, 205)
    ctab.canvas.set_roi("position", edited)
    ctab._save()

    saved = load_user_calibration(settings.game_version, settings.profile, ctab.calib["resolution"])
    assert saved is not None, "user calibration file not written"
    assert saved["rois"]["position"] == edited, f"roundtrip mismatch: {saved['rois']['position']}"
    print(f"• saved + round-tripped: position={saved['rois']['position']}")

    # resolve_calibration now prefers the user override
    resolved = resolve_calibration(settings.game_version, settings.profile, resolution=(2560, 1440))
    assert resolved["source"] == "user", f"expected user source, got {resolved['source']}"

    # Capture tab picked up the saved calibration
    assert window.capture_tab.calib["source"] == "user", "capture tab not refreshed"
    print("• capture tab refreshed to user calibration")

    # --- game capture-area picker ---
    ctab.mode_combo.setCurrentIndex(1)  # -> "Game capture area"
    assert "Game capture area" in ctab.canvas.get_rois(), "area box missing"
    # Reposition the capture region via the spinboxes
    ctab.sp_x.setValue(80); ctab.sp_y.setValue(100)
    ctab.sp_w.setValue(2400); ctab.sp_h.setValue(1440)
    go = ctab.calib["global_offsets"]
    assert go == {"top": 100, "left": 80, "width": 2400, "height": 1440}, go
    ctab._save()
    saved2 = load_user_calibration(settings.game_version, settings.profile, ctab.calib["resolution"])
    assert saved2["global_offsets"]["left"] == 80 and saved2["global_offsets"]["top"] == 100, saved2["global_offsets"]
    print(f"• game region saved: {saved2['global_offsets']}")
    ctab.mode_combo.setCurrentIndex(0)  # back to card regions
    assert "name" in ctab.canvas.get_rois(), "inner ROIs lost after area mode"
    print("• returned to card mode with inner ROIs intact")

    # --- auto-commit when leaving the Calibrate tab ---
    from PySide6.QtCore import Qt
    window._tabs.setCurrentIndex(window._calib_index)  # focus Calibrate
    ctab.roi_list.setCurrentItem(ctab.roi_list.findItems("height_weight", Qt.MatchExactly)[0])
    ctab.sp_x.setValue(2065)  # an edit -> marks dirty + updates the canvas
    assert ctab._dirty, "edit did not mark calibration dirty"
    window._tabs.setCurrentIndex(0)  # leave Calibrate -> should auto-commit
    assert not ctab._dirty, "auto-commit did not run on tab change"
    saved3 = load_user_calibration(settings.game_version, settings.profile, ctab.calib["resolution"])
    assert saved3["rois"]["height_weight"][2] == 2065, saved3["rois"]["height_weight"]
    print("• auto-committed calibration on tab change")

    window.close()
    print("\nPASS: calibration smoke test succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
