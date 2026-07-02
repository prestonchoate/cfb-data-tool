# SPDX-License-Identifier: GPL-3.0-or-later
"""Global hotkey bridged to a Qt signal.

The platform backend callback fires on its own thread; emitting a Qt signal from
there is delivered to the main thread via a queued connection. Global hooks can
require elevated privileges on some setups, so failures are swallowed — the
on-screen Scan button is always the reliable fallback.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..platform import get_hotkey_backend


class HotkeyManager(QObject):
    triggered = Signal()

    def __init__(self, key: str = "s", parent=None):
        super().__init__(parent)
        self._key = key
        self._backend = get_hotkey_backend()
        self._active = False

    def start(self) -> bool:
        self._active = self._backend.start(self._key, self.triggered.emit)
        return self._active

    def stop(self):
        if not self._active:
            return
        self._backend.stop()
        self._active = False
