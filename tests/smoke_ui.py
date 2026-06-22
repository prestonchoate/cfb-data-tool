# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless smoke test for the Phase 2 UI.

Runs the full UI path without a display (Qt 'offscreen' platform):
construct the app -> wait for the OCR engine -> load a fixture screenshot ->
Scan -> assert a valid result -> Save -> assert a CSV row was written.

    python tests/smoke_ui.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # no display needed
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from app.config.settings_store import Settings
from app.ui.main_window import MainWindow


def _first_fixture() -> str | None:
    root = Path(__file__).resolve().parent / "fixtures" / "screenshots"
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        for p in sorted(root.rglob(ext)):
            return str(p)
    return None


def _wait_until(app, predicate, timeout=120.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.05)
    return False


def main() -> int:
    fixture = _first_fixture()
    if not fixture:
        print("FAIL: no fixture screenshots found")
        return 1

    tmp = tempfile.mkdtemp()
    settings = Settings()
    settings.use_sounds = False
    settings.output_csv_path = os.path.join(tmp, "out.csv")
    settings.sqlite_path = os.path.join(tmp, "data.db")

    # Isolate from any real saved calibration and force the base 1440p resolution
    # so the bundled ROIs line up with the 2400x1440 fixture crop.
    import app.core.calibration as cal
    cal.USER_PRESETS_DIR = Path(tmp) / "presets"
    cal.detect_resolution = lambda *a, **k: (2560, 1440)

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(settings)
    window.show()
    cap = window.capture_tab

    print("• waiting for OCR engine…")
    if not _wait_until(app, lambda: cap.engine is not None, timeout=120):
        print("FAIL: engine did not initialize")
        return 1
    print("• engine ready")

    cap.load_image_path(fixture)
    assert cap.frame is not None, "frame not loaded"
    print(f"• loaded fixture: {Path(fixture).name}")

    cap.scan_now()
    print("• scanning…")
    if not _wait_until(app, lambda: cap.last_result is not None, timeout=60):
        print("FAIL: scan did not complete")
        return 1

    result = cap.last_result
    rec = result.record
    print(f"• scanned: {rec['NAME']} | {rec['POSITION']} | {rec['ARCHETYPE']} | "
          f"{rec['HEIGHT']} {rec['WEIGHT']} | {len(rec['attributes'])} attrs | "
          f"stars={rec['STARS']} | valid={result.valid}")
    if not result.valid:
        print(f"FAIL: expected a valid scan, missing={result.missing}")
        return 1

    cap.save_current()
    if window.store.count() != 1:
        print(f"FAIL: store has {window.store.count()} rows, expected 1")
        return 1
    saved = window.store.all()[0]
    print(f"• saved to store: {saved['name']} {saved['position']} ({window.store.count()} row)")

    window.close()
    print("\nPASS: UI smoke test succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
