# SPDX-License-Identifier: GPL-3.0-or-later
"""No-op hotkey backend (fallback when hooks are unavailable)."""

from __future__ import annotations

from typing import Callable


class NoopHotkey:
    def start(self, key: str, callback: Callable[[], None]) -> bool:
        return False

    def stop(self) -> None:
        pass
