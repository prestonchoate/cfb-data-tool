# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless smoke test for Phase 6 auto-capture + review queue.

Covers the detection logic (frame-diff: triggers on a stable+new card, not on a
repeat) and the review queue (enqueue, edit-sync, Save All with de-dupe, clear).
Does not exercise live screen capture or the OCR engine.

    python tests/smoke_autocapture.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

import app.config.settings_store as ss
import app.core.calibration as cal

_tmp = Path(tempfile.mkdtemp())
cal.USER_PRESETS_DIR = _tmp / "presets"
cal.detect_resolution = lambda *a, **k: (2560, 1440)
ss.CONFIG_DIR = _tmp
ss.SETTINGS_PATH = _tmp / "settings.json"

from PySide6.QtWidgets import QApplication

from app.config.settings_store import Settings
import app.core.profiles  # noqa: F401  (registers profiles)
from app.core.engine import ScanResult
from app.core.profiles.base import get_profile
from app.core.profiles.recruits import ATTRIBUTE_HEADERS, BASIC_INFO_HEADERS
from app.io.store import RecordStore
from app.ui.capture_tab import CaptureTab


def make_result(name, pos):
    rec = {h: "" for h in BASIC_INFO_HEADERS}
    rec.update({
        "NAME": name, "POSITION": pos, "ARCHETYPE": "Dual Threat", "STARS": 3,
        "GEM": "NORMAL", "HEIGHT": "6'2\"", "WEIGHT": "200", "CLASS": "High School",
        "HOMETOWN": "Town, ST", "DEV TRAIT": "",
    })
    rec["attributes"] = {ATTRIBUTE_HEADERS[i]: "80" for i in range(10)}
    rec["_confidence"] = {}
    valid, missing = get_profile("recruits").validate(rec)
    return ScanResult(record=rec, valid=valid, missing=missing, profile_key="recruits")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    store = RecordStore(str(_tmp / "data.db"), get_profile("recruits"))
    settings = Settings()
    settings.use_sounds = False
    cap = CaptureTab(settings, store)

    # --- detection: frame-diff sanity ---
    a = np.zeros((160, 805), dtype=np.uint8)
    assert cap._roi_diff(a, a.copy()) == 0.0
    diff_img = a.copy(); diff_img[:] = 200
    assert cap._roi_diff(a, diff_img) > 50
    print("• frame-diff sanity OK")

    # --- detection: triggers on a stable, new card; not on a repeat ---
    calls = []
    cap.scan_now = lambda auto=False: calls.append(auto)  # stub out the real scan
    cap.auto_capture = True
    cap.engine = object()
    cap.frame = np.zeros((1440, 2400, 3), dtype=np.uint8)
    cap._prev_name_roi = None
    cap._last_scan_name_roi = None
    cap._check_auto_capture()  # establishes previous frame, no trigger
    cap._check_auto_capture()  # stable + new -> trigger
    assert calls == [True], calls
    cap._check_auto_capture()  # same card as last capture -> no trigger
    assert calls == [True], calls
    print("• detection triggers once on a stable new card, not on the repeat")

    # --- review queue ---
    cap.scan_now = lambda auto=False: None
    cap._enqueue(make_result("John Doe", "QB"))
    cap._enqueue(make_result("Jane Smith", "WR"))
    cap._enqueue(make_result("John Doe", "QB"))  # duplicate name+position
    assert len(cap._queue) == 3, len(cap._queue)
    assert cap.queue_list.count() == 3
    print(f"• queued {len(cap._queue)} recruits (incl. 1 duplicate)")

    # edit-sync: editing the selected queue item updates the queue
    cap._on_queue_select(1)
    cap.result_card._on_edit("WEIGHT", "175")
    assert cap._queue[1]["WEIGHT"] == "175"
    print("• inline edit syncs back to the queued item")

    # remove just one (the duplicate at row 2) without clearing the rest
    cap.queue_list.setCurrentRow(2)
    cap._remove_selected()
    assert len(cap._queue) == 2 and cap.queue_list.count() == 2, len(cap._queue)
    assert [r["NAME"] for r in cap._queue] == ["John Doe", "Jane Smith"]
    print("• Remove Selected drops one entry, keeps the rest")

    cap._save_all()
    assert store.count() == 2, store.count()       # de-duped on save
    assert len(cap._queue) == 0 and cap.queue_list.count() == 0
    print(f"• Save All -> {store.count()} in collection (deduped); queue cleared")

    cap.shutdown()
    if cap._init_worker.isRunning():
        cap._init_worker.wait(20000)
    store.close()
    print("\nPASS: auto-capture smoke test succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
