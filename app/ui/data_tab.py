# SPDX-License-Identifier: GPL-3.0-or-later
"""Data tab: browse, filter, and export the scraped collection.

A sortable/filterable table over the SQLite RecordStore. Sorting is numeric-aware
(so STARS/WEIGHT/attributes sort as numbers), filtering matches across all columns.
Export writes the currently-visible (filtered) rows to CSV.
"""

from __future__ import annotations

import csv

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableView, QVBoxLayout, QWidget,
)


class _NumericProxy(QSortFilterProxyModel):
    """Sort numerically when both cells are numbers, else fall back to text."""

    def lessThan(self, left, right):
        l = self.sourceModel().data(left)
        r = self.sourceModel().data(right)
        try:
            return float(l) < float(r)
        except (TypeError, ValueError):
            return str(l) < str(r)


class DataTab(QWidget):
    def __init__(self, settings, store, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.store = store

        # Columns: ID + schema headers + Scanned
        self.display_headers = ["ID"] + store.headers + ["Scanned"]
        self.col_keys = ["id"] + store.columns + ["scanned_at"]

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText("Filter… (name, position, archetype, …)")
        self.filter_box.textChanged.connect(self._on_filter)
        bar.addWidget(self.filter_box, 1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self._delete_selected)
        self.export_btn = QPushButton("Export CSV…")
        self.export_btn.clicked.connect(self._export_csv)
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self._clear_all)
        for b in (self.refresh_btn, self.delete_btn, self.export_btn, self.clear_btn):
            bar.addWidget(b)
        root.addLayout(bar)

        self.model = QStandardItemModel(0, len(self.display_headers))
        self.model.setHorizontalHeaderLabels(self.display_headers)
        self.proxy = _NumericProxy()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)  # match across all columns
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnHidden(0, True)  # hide raw ID
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color:#888;")
        root.addWidget(self.count_label)

    # ---- data ------------------------------------------------------------
    def refresh(self):
        rows = self.store.all()
        self.model.setRowCount(0)
        for r in rows:
            items = []
            for key in self.col_keys:
                it = QStandardItem(str(r.get(key, "")))
                items.append(it)
            self.model.appendRow(items)
        self.count_label.setText(f"{len(rows)} recruit(s)")

    def _on_filter(self, text):
        self.proxy.setFilterFixedString(text)
        self.count_label.setText(f"{self.proxy.rowCount()} shown / {self.store.count()} total")

    def _selected_ids(self) -> list[int]:
        ids = []
        for idx in self.table.selectionModel().selectedRows():
            src = self.proxy.mapToSource(idx)
            ids.append(int(self.model.item(src.row(), 0).text()))
        return ids

    def _delete_selected(self):
        ids = self._selected_ids()
        if not ids:
            return
        if QMessageBox.question(self, "Delete", f"Delete {len(ids)} selected recruit(s)?") \
                != QMessageBox.Yes:
            return
        for row_id in ids:
            self.store.delete(row_id)
        self.refresh()

    def _clear_all(self):
        if self.store.count() == 0:
            return
        if QMessageBox.question(self, "Clear All",
                                "Delete ALL recruits from the collection?") != QMessageBox.Yes:
            return
        self.store.clear()
        self.refresh()

    def _export_csv(self):
        if self.proxy.rowCount() == 0:
            self.count_label.setText("Nothing to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", self.settings.output_csv_path, "CSV (*.csv)")
        if not path:
            return
        n = self.export_to(path)
        self.count_label.setText(f"Exported {n} recruit(s) to {path}")

    def export_to(self, path) -> int:
        """Write the schema columns of the currently-visible (filtered/sorted) rows
        to a CSV at ``path``. Returns the number of rows written."""
        schema_cols = list(range(1, 1 + len(self.store.headers)))  # skip ID at col 0
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.store.headers)
            for prow in range(self.proxy.rowCount()):
                writer.writerow(
                    [self.proxy.data(self.proxy.index(prow, c)) or "" for c in schema_cols])
        return self.proxy.rowCount()
