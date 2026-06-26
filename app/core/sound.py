# SPDX-License-Identifier: GPL-3.0-or-later
"""Play notification sounds (cross-platform).

A "sound spec" is a path to a .wav/.aiff file. On Windows the sounds ship in
the Media folder; on macOS they live in /System/Library/Sounds. Playback is
async (non-blocking) and routes through the default audio device. No-ops
cleanly when no audio is available.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_IS_WIN = sys.platform == "win32"
_IS_MAC = sys.platform == "darwin"

WINDOWS_MEDIA = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Media"
MACOS_SOUNDS = Path("/System/Library/Sounds")

_SOUND_EXTS = ("*.wav",) if _IS_WIN else ("*.aiff", "*.wav") if _IS_MAC else ("*.wav",)


def list_media_sounds() -> dict[str, str]:
    """Return {display_name: path} for system sounds on the current platform."""
    out: dict[str, str] = {}
    if _IS_WIN and WINDOWS_MEDIA.exists():
        for f in sorted(WINDOWS_MEDIA.glob("*.wav"), key=lambda p: p.stem.lower()):
            out[f.stem] = str(f)
    elif _IS_MAC and MACOS_SOUNDS.exists():
        for f in sorted(MACOS_SOUNDS.iterdir(), key=lambda p: p.stem.lower()):
            if f.suffix.lower() in (".aiff", ".wav"):
                out[f.stem] = str(f)
    return out


def is_sound_file(spec: str) -> bool:
    if not spec:
        return False
    suffix = Path(spec).suffix.lower()
    return suffix in (".wav", ".aiff")


def _first_existing(names: list[str]) -> str:
    if _IS_WIN:
        folder = WINDOWS_MEDIA
    elif _IS_MAC:
        folder = MACOS_SOUNDS
    else:
        return ""
    for n in names:
        p = folder / n
        if p.exists():
            return str(p)
    sounds = list_media_sounds()
    return next(iter(sounds.values()), "")


def default_success() -> str:
    if _IS_WIN:
        return _first_existing(
            ["tada.wav", "Windows Notify.wav", "Windows Notify System Generic.wav", "chimes.wav"])
    elif _IS_MAC:
        return _first_existing(["Glass.aiff", "Hero.aiff", "Ping.aiff"])
    return ""


def default_fail() -> str:
    if _IS_WIN:
        return _first_existing(
            ["Windows Critical Stop.wav", "chord.wav", "Windows Background.wav"])
    elif _IS_MAC:
        return _first_existing(["Basso.aiff", "Sosumi.aiff", "Funk.aiff"])
    return ""


def play_sound(spec: str) -> None:
    if not spec or not Path(spec).exists():
        return
    try:
        if _IS_WIN:
            import winsound
            if is_sound_file(spec):
                winsound.PlaySound(spec, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                winsound.PlaySound(spec, winsound.SND_ALIAS | winsound.SND_ASYNC)
        elif _IS_MAC:
            subprocess.Popen(
                ["afplay", spec],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:  # noqa: BLE001
        pass
