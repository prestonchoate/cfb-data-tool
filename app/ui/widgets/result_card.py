# SPDX-License-Identifier: GPL-3.0-or-later
"""Result card: shows a ScanResult and lets the user correct it before saving.

Each field is editable. OCR fields are outlined by confidence (green / amber /
red vs the threshold) so low-confidence misreads stand out; the user fixes them
inline and the corrected values are what get saved. Editing re-validates and
updates the VALID/INVALID banner live.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import QRegularExpression, Qt, Signal
from PySide6.QtGui import QIntValidator, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from ...core.profiles.recruits import (
    ATTRIBUTE_HEADERS, BASIC_INFO_HEADERS, MENTAL_NAMES, POSITION_ATTRIBUTE_COUNT,
    POSITIONS, get_position_archetypes,
)

_GEM_OPTIONS = ["NORMAL", "GEM", "BUST"]
_DEV_OPTIONS = ["", "Normal", "Impact", "Star", "Elite"]
_LEVEL_OPTIONS = ["", "Bronze", "Silver", "Gold", "Platinum"]
_HEIGHT_RE = QRegularExpression(r'^[3-8]\'(1[01]|\d)"$')


def _conf_color(conf, threshold: float):
    if conf is None:
        return None
    if conf >= 0.90:
        return "#2e7d32"  # green
    if conf >= threshold:
        return "#f9a825"  # amber
    return "#c62828"      # red


_BORDER_PX = 1


def _field_height() -> int:
    """Smallest row height every field type can share.

    QComboBox/QSpinBox render arrow/spinner buttons at a fixed native size —
    forcing them smaller or larger than their own sizeHint produces visible
    rendering artifacts on some platform styles, so that height is treated as
    a floor and left untouched. Every other field is then shrunk/grown to
    match it, so the whole form lines up at the smallest height that still
    fits the arrows cleanly.
    """
    combo_h = QComboBox().sizeHint().height()
    spin_h = QSpinBox().sizeHint().height()
    return max(combo_h, spin_h) + 2 * _BORDER_PX


def _bordered(widget, color):
    """Outline *widget* with a confidence-colored border, sized to the
    shared row height.

    QComboBox/QSpinBox lose their native dropdown arrow / spin buttons as
    soon as a stylesheet touches them directly, so those are wrapped in a
    bordered frame instead of styled in place. Both default to a Fixed
    vertical size policy and don't share an identical natural sizeHint, so
    without an explicit height the smaller of the two leaves a gap inside
    the frame — pin it to the same inner height (frame height minus the
    border) so combo and spin boxes fill their frame identically.
    Always wrapped (transparent border when there's no confidence color) so
    sizing stays consistent whether or not a border is shown.
    """
    target = _field_height()
    if isinstance(widget, (QComboBox, QSpinBox)):
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame{{border:{_BORDER_PX}px solid {color or 'transparent'}; border-radius:3px;}}")
        frame.setFixedHeight(target)
        widget.setFixedHeight(target - 2 * _BORDER_PX)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        return frame
    widget.setFixedHeight(target)
    if color:
        widget.setStyleSheet(f"border:1px solid {color}; border-radius:3px;")
    return widget


class ResultCard(QWidget):
    changed = Signal()  # emitted when the user edits any field

    def __init__(self, confidence_threshold: float = 0.80, profile=None, parent=None):
        super().__init__(parent)
        self.threshold = confidence_threshold
        self.profile = profile
        self._record: dict | None = None
        self._field_widgets: dict = {}
        self._ability_widgets: dict = {}
        self._mental_widgets: dict = {}
        self._attr_widgets: dict = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        inner = QWidget()
        root = QVBoxLayout(inner)

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

        self._abilities_box = QGroupBox("Abilities")
        self._abilities_box.setVisible(False)
        self._abilities = QGridLayout(self._abilities_box)
        root.addWidget(self._abilities_box)

        self._mentals_box = QGroupBox("Mentals")
        self._mentals_box.setVisible(False)
        self._mentals = QGridLayout(self._mentals_box)
        root.addWidget(self._mentals_box)

        attrs_box = QGroupBox("Attributes")
        self._attrs = QGridLayout(attrs_box)
        root.addWidget(attrs_box)

        root.addStretch(1)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    # ---- public API ------------------------------------------------------
    def show_result(self, result):
        self.show_record(result.record)

    def show_record(self, record):
        """Display a plain record (used for reviewing a queued auto-capture)."""
        self._record = copy.deepcopy(record)
        self._field_widgets.clear()
        self._ability_widgets.clear()
        self._mental_widgets.clear()
        self._attr_widgets.clear()
        self._build_basics()
        self._build_abilities()
        self._build_mentals()
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
            color = _conf_color(conf.get(key), self.threshold)
            self._field_widgets[key] = widget
            self._basics.addWidget(label, row, 0)
            self._basics.addWidget(_bordered(widget, color), row, 1)

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
        if key == "POSITION":
            cb = QComboBox()
            cb.addItems([""] + POSITIONS)
            cb.setCurrentText(str(value) if str(value) in POSITIONS else "")
            cb.currentTextChanged.connect(lambda v, k=key: self._on_edit(k, v))
            cb.currentTextChanged.connect(self._on_position_changed)
            return cb
        if key == "ARCHETYPE":
            cb = QComboBox()
            options = self._archetype_options(self._record.get("POSITION", ""))
            cb.addItems(options)
            cb.setCurrentText(str(value) if str(value) in options else "")
            cb.currentTextChanged.connect(lambda v, k=key: self._on_edit(k, v))
            return cb
        if key == "HEIGHT":
            le = QLineEdit(str(value))
            le.setValidator(QRegularExpressionValidator(_HEIGHT_RE))
            le.textEdited.connect(lambda v, k=key: self._on_edit(k, v))
            return le
        if key == "WEIGHT":
            le = QLineEdit(str(value))
            le.setValidator(QIntValidator(1, 400))
            le.textEdited.connect(lambda v, k=key: self._on_edit(k, v))
            return le
        le = QLineEdit(str(value))
        le.textEdited.connect(lambda v, k=key: self._on_edit(k, v))
        return le

    def _archetype_options(self, position: str) -> list[str]:
        return [""] + get_position_archetypes(position)

    def _on_position_changed(self, new_position):
        archetype_cb = self._field_widgets.get("ARCHETYPE")
        if not isinstance(archetype_cb, QComboBox):
            return
        current = archetype_cb.currentText()
        options = self._archetype_options(new_position)
        archetype_cb.blockSignals(True)
        archetype_cb.clear()
        archetype_cb.addItems(options)
        archetype_cb.setCurrentText(current if current in options else "")
        archetype_cb.blockSignals(False)
        self._on_edit("ARCHETYPE", archetype_cb.currentText())

    def _build_abilities(self):
        self._clear(self._abilities)
        abilities = self._record.get("abilities", {})
        self._abilities_box.setVisible(bool(abilities))
        color = _conf_color(self._record.get("_confidence", {}).get("abilities"), self.threshold)
        for row, (name, level) in enumerate(abilities.items()):
            name_edit = QLineEdit(str(name))
            name_edit.textEdited.connect(
                lambda v, old=name: self._on_ability_name_edit(old, v))
            level_cb = QComboBox()
            level_cb.addItems(_LEVEL_OPTIONS)
            if str(level) in _LEVEL_OPTIONS:
                level_cb.setCurrentText(str(level))
            level_cb.currentTextChanged.connect(
                lambda v, n=name: self._on_ability_level_edit(n, v))
            self._ability_widgets[name] = (name_edit, level_cb)
            self._abilities.addWidget(_bordered(name_edit, color), row, 0)
            self._abilities.addWidget(_bordered(level_cb, color), row, 1)

    def _build_mentals(self):
        self._clear(self._mentals)
        mentals = self._record.get("mentals", {})
        self._mentals_box.setVisible(bool(mentals))
        color = _conf_color(self._record.get("_confidence", {}).get("mentals"), self.threshold)
        for row, (name, level) in enumerate(mentals.items()):
            name_cb = QComboBox()
            name_cb.addItems([""] + MENTAL_NAMES)
            name_cb.setCurrentText(str(name) if str(name) in MENTAL_NAMES else "")
            name_cb.currentTextChanged.connect(
                lambda v, old=name: self._on_mental_name_edit(old, v))
            level_cb = QComboBox()
            level_cb.addItems(_LEVEL_OPTIONS)
            if str(level) in _LEVEL_OPTIONS:
                level_cb.setCurrentText(str(level))
            level_cb.currentTextChanged.connect(
                lambda v, n=name: self._on_mental_level_edit(n, v))
            self._mental_widgets[name] = (name_cb, level_cb)
            self._mentals.addWidget(_bordered(name_cb, color), row, 0)
            self._mentals.addWidget(_bordered(level_cb, color), row, 1)

    def _build_attrs(self):
        self._clear(self._attrs)
        attrs = self._record.get("attributes", {})
        items = list(attrs.items())
        expected = POSITION_ATTRIBUTE_COUNT.get(self._record.get("POSITION"), 10)
        total = max(expected, len(items))
        half = (total + 1) // 2

        attr_conf = self._record.get("_confidence", {}).get("attributes")
        attr_color = _conf_color(attr_conf, self.threshold)

        present = {k.upper() for k in attrs}
        options = [""] + sorted(h.title() for h in ATTRIBUTE_HEADERS if h not in present)
        self._missing_attr_pairs = []

        for i in range(total):
            col = 0 if i < half else 2
            row = i if i < half else i - half
            if i < len(items):
                name, value = items[i]
                label = QLabel(name.title())
                label.setStyleSheet("color:#aaa;")
                le = QLineEdit(str(value))
                le.setMaximumWidth(64)
                le.setValidator(QIntValidator(1, 99))
                le.textEdited.connect(lambda v, a=name: self._on_attr_edit(a, v))
                self._attr_widgets[name] = le
                self._attrs.addWidget(label, row, col)
                self._attrs.addWidget(_bordered(le, attr_color), row, col + 1)
            else:
                pair_idx = len(self._missing_attr_pairs)
                cb = QComboBox()
                cb.addItems(options)
                le = QLineEdit()
                le.setValidator(QIntValidator(1, 99))
                le.setMaximumWidth(64)
                le.setPlaceholderText("?")
                self._missing_attr_pairs.append((cb, le))
                cb.currentTextChanged.connect(
                    lambda _, pi=pair_idx: self._on_missing_attr_changed(pi))
                le.textEdited.connect(
                    lambda _, pi=pair_idx: self._on_missing_attr_changed(pi))
                self._attrs.addWidget(_bordered(cb, "#c62828"), row, col)
                self._attrs.addWidget(_bordered(le, None), row, col + 1)

    # ---- edits -----------------------------------------------------------
    def _on_edit(self, key, value):
        self._record[key] = int(value) if key == "STARS" else value
        self._update_banner()
        self.changed.emit()

    def _on_ability_name_edit(self, old_name, new_name):
        abilities = self._record.get("abilities", {})
        if old_name in abilities:
            level = abilities.pop(old_name)
            abilities[new_name] = level
        self.changed.emit()

    def _on_ability_level_edit(self, name, level):
        self._record.setdefault("abilities", {})[name] = level
        self.changed.emit()

    def _on_mental_name_edit(self, old_name, new_name):
        mentals = self._record.get("mentals", {})
        if old_name in mentals:
            level = mentals.pop(old_name)
            mentals[new_name] = level
        self.changed.emit()

    def _on_mental_level_edit(self, name, level):
        self._record.setdefault("mentals", {})[name] = level
        self.changed.emit()

    def _on_missing_attr_changed(self, pair_idx):
        cb, le = self._missing_attr_pairs[pair_idx]
        name = cb.currentText()
        raw = le.text().lstrip("0") or ""
        if raw != le.text():
            le.setText(raw)
        if name and raw:
            self._record.setdefault("attributes", {})[name] = raw
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
