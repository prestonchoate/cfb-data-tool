# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings tab. A focused subset for Phase 2; grows with later phases.

Surfaces what the original CLI asked at startup (output target, sounds) plus the
monitor, hotkey, auto-save, and confidence threshold — all persisted to JSON so
users never touch a .py file.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from ..platform.detect import desktop_target
from .widgets.hotkey_edit import HotkeyEdit
from .widgets.sound_picker import SoundPicker


class SettingsTab(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        # (Game monitor lives in the Calibrate tab, where you capture it.)

        # Scans always go into the SQLite collection (Data tab). This sets the
        # default location for CSV exports from there.
        path_row = QHBoxLayout()
        self.csv_path = QLineEdit(settings.output_csv_path)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_csv)
        path_row.addWidget(self.csv_path)
        path_row.addWidget(browse)
        form.addRow("Default export CSV:", path_row)

        # Hotkey — click and press a key to capture it
        self.hotkey = HotkeyEdit(settings.hotkey)
        form.addRow("Scan hotkey:", self.hotkey)

        # Confidence threshold
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.0, 1.0)
        self.threshold.setSingleStep(0.05)
        self.threshold.setValue(settings.confidence_threshold)
        form.addRow("Flag fields below confidence:", self.threshold)

        # Sounds
        self.sounds = QCheckBox("Play success/fail sounds")
        self.sounds.setChecked(settings.use_sounds)
        self.sounds.toggled.connect(self._on_sounds_toggled)
        form.addRow(self.sounds)

        self.success_picker = SoundPicker(settings.success_sound)
        form.addRow("Success sound:", self.success_picker)
        self.fail_picker = SoundPicker(settings.fail_sound)
        form.addRow("Fail sound:", self.fail_picker)
        self._on_sounds_toggled(settings.use_sounds)

        self.auto_save = QCheckBox("Auto-save valid scans")
        self.auto_save.setChecked(settings.auto_save_valid)
        form.addRow(self.auto_save)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self.save_btn = QPushButton("Save settings")
        self.save_btn.clicked.connect(self._save)
        save_row.addWidget(self.save_btn)
        root.addLayout(save_row)

        self.note = QLabel("")
        self.note.setStyleSheet("color:#2e7d32;")
        root.addWidget(self.note)

        if desktop_target() == "linux_wayland":
            linux_note = QLabel(
                "Linux (Wayland): live capture requires a one-time portal permission per "
                "session. Global hotkeys may be unavailable — use the Scan button.")
            linux_note.setWordWrap(True)
            linux_note.setStyleSheet("color:#666;")
            root.addWidget(linux_note)

        root.addStretch(1)

    def _browse_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Output CSV", self.csv_path.text(), "CSV (*.csv)")
        if path:
            self.csv_path.setText(path)

    def _on_sounds_toggled(self, on: bool):
        self.success_picker.setEnabled(on)
        self.fail_picker.setEnabled(on)

    def _save(self):
        s = self.settings
        s.output_csv_path = self.csv_path.text()
        s.hotkey = self.hotkey.text().strip() or "s"
        s.confidence_threshold = round(self.threshold.value(), 2)
        s.use_sounds = self.sounds.isChecked()
        s.success_sound = self.success_picker.value()
        s.fail_sound = self.fail_picker.value()
        s.auto_save_valid = self.auto_save.isChecked()
        s.save()
        self.note.setText("Saved. (Hotkey changes apply after restart.)")
