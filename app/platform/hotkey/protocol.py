# SPDX-License-Identifier: GPL-3.0-or-later
"""Hotkey backend protocol."""

from __future__ import annotations

from typing import Callable, Protocol


class HotkeyBackend(Protocol):
    def start(self, key: str, callback: Callable[[], None]) -> bool:
        ...

    def stop(self) -> None:
        ...
