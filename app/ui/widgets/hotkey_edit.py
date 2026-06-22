# SPDX-License-Identifier: GPL-3.0-or-later
"""A click-to-capture hotkey field.

Instead of typing a key name, the user clicks the field and presses the key they
want; it fills in the name the ``keyboard`` library understands (e.g. pressing
INSERT fills "insert", Ctrl+S fills "ctrl+s").
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

# Qt special keys -> names the `keyboard` library understands.
_SPECIAL = {
    Qt.Key_Insert: "insert", Qt.Key_Delete: "delete",
    Qt.Key_Home: "home", Qt.Key_End: "end",
    Qt.Key_PageUp: "page up", Qt.Key_PageDown: "page down",
    Qt.Key_Up: "up", Qt.Key_Down: "down", Qt.Key_Left: "left", Qt.Key_Right: "right",
    Qt.Key_Escape: "esc", Qt.Key_Space: "space", Qt.Key_Tab: "tab",
    Qt.Key_Return: "enter", Qt.Key_Enter: "enter", Qt.Key_Backspace: "backspace",
    Qt.Key_CapsLock: "caps lock", Qt.Key_Print: "print screen",
    Qt.Key_ScrollLock: "scroll lock", Qt.Key_Pause: "pause",
    Qt.Key_NumLock: "num lock", Qt.Key_Menu: "menu",
}
for _i in range(1, 25):
    _key = getattr(Qt, f"Key_F{_i}", None)
    if _key is not None:
        _SPECIAL[_key] = f"f{_i}"

_MODIFIER_KEYS = {
    Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta,
    Qt.Key_AltGr, Qt.Key_Super_L, Qt.Key_Super_R,
}


class HotkeyEdit(QLineEdit):
    def __init__(self, value: str = "", parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setText(value)
        self.setPlaceholderText("Click, then press a key…")
        self.setToolTip("Click here and press the key you want to use to scan.")
        self._captured = False
        self._previous = value

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._captured = False
        self._previous = self.text()
        self.clear()  # reveal the "press a key…" prompt

    def focusOutEvent(self, event):
        if not self._captured and not self.text():
            self.setText(self._previous)  # nothing pressed -> keep the old value
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if event.key() in _MODIFIER_KEYS:
            return  # wait for a real key, not a bare modifier
        name = self._key_name(event)
        if not name:
            return
        mods = []
        m = event.modifiers()
        if m & Qt.ControlModifier:
            mods.append("ctrl")
        if m & Qt.AltModifier:
            mods.append("alt")
        if m & Qt.ShiftModifier:
            mods.append("shift")
        self.setText("+".join(mods + [name]))
        self._captured = True
        self.clearFocus()

    @staticmethod
    def _key_name(event):
        qkey = event.key()
        if qkey in _SPECIAL:
            return _SPECIAL[qkey]
        # Use the key code (not event.text()) for letters/digits: with Ctrl held,
        # text() is a control character (Ctrl+S -> "\x13"), not "s".
        key = int(qkey)
        if int(Qt.Key_A) <= key <= int(Qt.Key_Z):
            return chr(key).lower()
        if int(Qt.Key_0) <= key <= int(Qt.Key_9):
            return chr(key)
        text = event.text()
        if text and text.isprintable() and not text.isspace():
            return text.lower()
        return None
