# SPDX-License-Identifier: GPL-3.0-or-later
"""Global hotkey via the keyboard library."""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)


class KeyboardHotkey:
    def __init__(self) -> None:
        self._handle = None

    def start(self, key: str, callback: Callable[[], None]) -> bool:
        try:
            import keyboard
            self._handle = keyboard.add_hotkey(key, callback)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Global hotkey '%s' unavailable: %s", key, exc)
            self._handle = None
            return False

    def stop(self) -> None:
        if self._handle is None:
            return
        try:
            import keyboard
            keyboard.remove_hotkey(self._handle)
        except Exception:  # noqa: BLE001
            pass
        self._handle = None
