# SPDX-License-Identifier: GPL-3.0-or-later
"""Play notification sounds (cross-platform).

A "sound spec" is a path to a .wav/.aiff/.oga file. Playback is async
(non-blocking) and routes through the default audio device. No-ops cleanly when
no audio is available.
"""

from __future__ import annotations

from pathlib import Path

from ..platform.sound import get_sound_backend


def list_media_sounds() -> dict[str, str]:
    return get_sound_backend().list_media_sounds()


def is_sound_file(spec: str) -> bool:
    if not spec:
        return False
    suffix = Path(spec).suffix.lower()
    return suffix in (".wav", ".aiff", ".oga", ".ogg")


def default_success() -> str:
    return get_sound_backend().default_success()


def default_fail() -> str:
    return get_sound_backend().default_fail()


def play_sound(spec: str) -> None:
    get_sound_backend().play_sound(spec)
