# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless smoke test for the Phase 4 data store + Data tab.

Covers: upsert with de-dupe on NAME+POSITION, update-in-place, the Data tab
table/filter, CSV export of the visible rows, and delete.

    python tests/smoke_data.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from app.config.settings_store import Settings
import app.core.profiles  # noqa: F401  (registers built-in profiles)
from app.core.profiles.base import get_profile
from app.core.profiles.recruits import BASIC_INFO_HEADERS
from app.io.store import RecordStore
from app.ui.data_tab import DataTab


def make_record(name, pos, stars=3, speed="90"):
    rec = {h: "" for h in BASIC_INFO_HEADERS}
    rec.update({
        "NAME": name, "POSITION": pos, "ARCHETYPE": "Dual Threat", "STARS": stars,
        "GEM": "NORMAL", "HEIGHT": "6'2\"", "WEIGHT": "200", "CLASS": "High School",
        "HOMETOWN": "Town, ST", "DEV TRAIT": "",
    })
    rec["attributes"] = {"SPEED": speed, "STRENGTH": "80"}
    return rec


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    tmp = Path(tempfile.mkdtemp())
    settings = Settings()
    settings.output_csv_path = str(tmp / "out.csv")
    profile = get_profile("recruits")
    store = RecordStore(str(tmp / "data.db"), profile)

    # De-dupe on NAME+POSITION
    assert store.upsert(profile.to_row(make_record("John Doe", "QB"))) == "inserted"
    assert store.upsert(profile.to_row(make_record("John Doe", "QB", stars=5, speed="99"))) == "updated"
    assert store.count() == 1, store.count()
    store.upsert(profile.to_row(make_record("Jane Smith", "WR")))
    assert store.count() == 2
    print("• dedupe OK: 2 records after 3 upserts (1 was an update)")

    john = [r for r in store.all() if r["name"] == "John Doe"][0]
    assert john["stars"] == "5" and john["speed"] == "99", john
    print("• update-in-place applied: John Doe stars=5 speed=99")

    dt = DataTab(settings, store)
    dt.refresh()
    assert dt.model.rowCount() == 2, dt.model.rowCount()
    dt.filter_box.setText("Jane")
    assert dt.proxy.rowCount() == 1, dt.proxy.rowCount()
    dt.filter_box.setText("")
    print("• Data tab: 2 rows; filter 'Jane' -> 1 shown")

    csv_path = tmp / "export.csv"
    n = dt.export_to(str(csv_path))
    assert csv_path.exists() and n == 2, n
    header = csv_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header[:2] == ["NAME", "POSITION"], header
    print(f"• exported {n} rows to CSV ({len(header)} columns)")

    jane_id = [r["id"] for r in store.all() if r["name"] == "Jane Smith"][0]
    store.delete(jane_id)
    dt.refresh()
    assert store.count() == 1 and dt.model.rowCount() == 1
    print("• delete OK: 1 record remains")

    store.close()
    print("\nPASS: data smoke test succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
