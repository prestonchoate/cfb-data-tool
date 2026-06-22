# SPDX-License-Identifier: GPL-3.0-or-later
"""Result card: shows a ScanResult and lets the user correct it before saving.

Each field is editable. OCR fields are outlined by confidence (green / amber /
red vs the threshold) so low-confidence misreads stand out; the user fixes them
inline and the corrected values are what get saved. Editing re-validates and
updates the VALID/INVALID banner live.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QGroupBox, QLabel, QLineEdit, QSpinBox, QVBoxLayout,
    QWidget,
)

from ...core.profiles.recruits import BASIC_INFO_HEADERS

# Fields produced by computer vision (not OCR) have no confidence score.
_CV_FIELDS = {"STARS", "GEM"}
_GEM_OPTIONS = ["NORMAL", "GEM", "BUST"]
_DEV_OPTIONS = ["", "Normal", "Impact", "Star", "Elite"]


def _conf_color(conf, threshold: float):
    if conf is None:
        return None
    if conf >= 0.90:
        return "#2e7d32"  # green
    if conf >= threshold:
        return "#f9a825"  # amber
    return "#c62828"      # red


class ResultCard(QWidget):
    changed = Signal()  # emitted when the user edits any field

    def __init__(self, confidence_threshold: float = 0.80, profile=None, parent=None):
        super().__init__(parent)
        self.threshold = confidence_threshold
        self.profile = profile
        self._record: dict | None = None
        self._field_widgets: dict = {}
        self._attr_widgets: dict = {}

        root = QVBoxLayout(self)

        self.status = QLabel("No scan yet")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet("font-weight:bold; padding:6px; border-radius:4px;")
        root.addWidget(self.status)

        hint = QLabel("Outlined fields are low-confidence. Edit any field to correct it before saving.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888; font-size:11px;")
        root.addWidget(hint)

        basics_box = QGroupBox("Recruit")
        self._basics = QGridLayout(basics_box)
        self._basics.setColumnStretch(1, 1)
        root.addWidget(basics_box)

        attrs_box = QGroupBox("Attributes")
        self._attrs = QGridLayout(attrs_box)
        root.addWidget(attrs_box)

        root.addStretch(1)

    # ---- public API ------------------------------------------------------
    def show_result(self, result):
        self._record = copy.deepcopy(result.record)
        self._field_widgets.clear()
        self._attr_widgets.clear()
        self._build_basics()
        self._build_attrs()
        self._update_banner()

    def edited_record(self) -> dict | None:
        """The record with any user corrections applied (what should be saved)."""
        return self._record

    # ---- build widgets ---------------------------------------------------
    def _clear(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _build_basics(self):
        self._clear(self._basics)
        conf = self._record.get("_confidence", {})
        for row, key in enumerate(BASIC_INFO_HEADERS):
            label = QLabel(key.title())
            label.setStyleSheet("color:#aaa;")
            widget = self._make_widget(key, self._record.get(key, ""))
            c = None if key in _CV_FIELDS else conf.get(key)
            color = _conf_color(c, self.threshold)
            if color:
                widget.setStyleSheet(f"border:1px solid {color}; border-radius:3px;")
            self._field_widgets[key] = widget
            self._basics.addWidget(label, row, 0)
            self._basics.addWidget(widget, row, 1)

    def _make_widget(self, key, value):
        if key == "STARS":
            sp = QSpinBox()
            sp.setRange(0, 5)
            try:
                sp.setValue(int(value))
            except (TypeError, ValueError):
                sp.setValue(0)
            sp.valueChanged.connect(lambda v, k=key: self._on_edit(k, v))
            return sp
        if key == "GEM":
            cb = QComboBox()
            cb.addItems(_GEM_OPTIONS)
            if str(value) in _GEM_OPTIONS:
                cb.setCurrentText(str(value))
            cb.currentTextChanged.connect(lambda v, k=key: self._on_edit(k, v))
            return cb
        if key == "DEV TRAIT":
            cb = QComboBox()
            cb.addItems(_DEV_OPTIONS)
            cb.setCurrentText(str(value) if str(value) in _DEV_OPTIONS else "")
            cb.currentTextChanged.connect(lambda v, k=key: self._on_edit(k, v))
            return cb
        le = QLineEdit(str(value))
        le.textEdited.connect(lambda v, k=key: self._on_edit(k, v))
        return le

    def _build_attrs(self):
        self._clear(self._attrs)
        items = list(self._record.get("attributes", {}).items())
        half = (len(items) + 1) // 2
        for i, (name, value) in enumerate(items):
            col = 0 if i < half else 2
            row = i if i < half else i - half
            label = QLabel(name.title())
            label.setStyleSheet("color:#aaa;")
            le = QLineEdit(str(value))
            le.setMaximumWidth(64)
            le.textEdited.connect(lambda v, a=name: self._on_attr_edit(a, v))
            self._attr_widgets[name] = le
            self._attrs.addWidget(label, row, col)
            self._attrs.addWidget(le, row, col + 1)

    # ---- edits -----------------------------------------------------------
    def _on_edit(self, key, value):
        self._record[key] = int(value) if key == "STARS" else value
        self._update_banner()
        self.changed.emit()

    def _on_attr_edit(self, attr, value):
        self._record.setdefault("attributes", {})[attr] = value
        self.changed.emit()

    def _update_banner(self):
        if not self.profile or self._record is None:
            return
        valid, missing = self.profile.validate(self._record)
        if valid:
            self.status.setText("✔ VALID")
            self.status.setStyleSheet(
                "font-weight:bold; padding:6px; border-radius:4px; background:#2e7d32; color:white;")
        else:
            self.status.setText("✘ INVALID — " + ", ".join(missing))
            self.status.setStyleSheet(
                "font-weight:bold; padding:6px; border-radius:4px; background:#c62828; color:white;")
