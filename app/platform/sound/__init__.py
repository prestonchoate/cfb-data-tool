# SPDX-License-Identifier: GPL-3.0-or-later
"""Sound backend factory."""

from __future__ import annotations

import sys

from .protocol import SoundBackend

_backend: SoundBackend | None = None


def get_sound_backend() -> SoundBackend:
    global _backend
    if _backend is None:
        if sys.platform == "win32":
            from .windows import WindowsSound
            _backend = WindowsSound()
        elif sys.platform == "darwin":
            from .macos import MacSound
            _backend = MacSound()
        else:
            from .linux import LinuxSound
            _backend = LinuxSound()
    return _backend
