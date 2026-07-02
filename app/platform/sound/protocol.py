# SPDX-License-Identifier: GPL-3.0-or-later
"""Sound backend protocol."""

from __future__ import annotations

from typing import Protocol


class SoundBackend(Protocol):
    def list_media_sounds(self) -> dict[str, str]:
        ...

    def default_success(self) -> str:
        ...

    def default_fail(self) -> str:
        ...

    def play_sound(self, spec: str) -> None:
        ...
