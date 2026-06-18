# SPDX-License-Identifier: GPL-3.0-or-later
"""Generic CSV output. Works for any profile given its schema (column headers)."""

from __future__ import annotations

import csv
import os


class CSVManager:
    def __init__(self, filename: str, headers: list[str]):
        self.filename = filename
        self.headers = headers
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.filename):
            with open(self.filename, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self.headers)

    def save_row(self, row: list):
        with open(self.filename, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
