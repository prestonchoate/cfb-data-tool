# SPDX-License-Identifier: GPL-3.0-or-later
"""A sound chooser: pick a Windows system sound or a custom .wav, with preview."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QPushButton, QWidget

from ...core.sound import is_sound_file, list_media_sounds, play_sound

_CUSTOM_LABEL = "Custom .wav file…"


class SoundPicker(QWidget):
    def __init__(self, value: str = "", parent=None):
        super().__init__(parent)
        self._value = value
        self._prev_index = 0

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.combo = QComboBox()
        for name, path in list_media_sounds().items():
            self.combo.addItem(name, path)
        self.combo.addItem(_CUSTOM_LABEL, None)
        self._custom_index = self.combo.count() - 1
        self.combo.activated.connect(self._on_activated)

        self.test_btn = QPushButton("▶")
        self.test_btn.setFixedWidth(30)
        self.test_btn.setToolTip("Preview this sound")
        self.test_btn.clicked.connect(lambda: play_sound(self._value))

        lay.addWidget(self.combo, 1)
        lay.addWidget(self.test_btn)

        self.set_value(value)

    def value(self) -> str:
        return self._value

    def set_value(self, value: str):
        self._value = value
        for i in range(self._custom_index):
            if self.combo.itemData(i) == value:
                self.combo.setCurrentIndex(i)
                self._prev_index = i
                return
        if is_sound_file(value):
            self._show_custom(value)
        elif self._custom_index > 0:  # unknown/alias -> first available media sound
            self.combo.setCurrentIndex(0)
            self._value = self.combo.itemData(0)
            self._prev_index = 0

    def _show_custom(self, path: str):
        self.combo.setItemText(self._custom_index, f"Custom: {Path(path).name}")
        self.combo.setItemData(self._custom_index, path)
        self.combo.setCurrentIndex(self._custom_index)
        self._value = path
        self._prev_index = self._custom_index

    def _on_activated(self, index: int):
        if index == self._custom_index:
            path, _ = QFileDialog.getOpenFileName(
                self, "Choose a sound file", "", "Audio files (*.wav *.aiff)")
            if path:
                self._show_custom(path)
            else:
                self.combo.setCurrentIndex(self._prev_index)  # cancelled
        else:
            self._value = self.combo.itemData(index)
            self._prev_index = index
