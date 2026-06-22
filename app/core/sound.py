# SPDX-License-Identifier: GPL-3.0-or-later
"""Play notification sounds.

A "sound spec" is a path to a .wav file (e.g. one of the files in the Windows
Media folder, or the user's own). Playback is async (non-blocking) and routes
through the default audio device. No-ops cleanly off Windows or without audio.

Earlier versions used Windows system-sound *aliases* (SystemAsterisk, ...), but
Windows maps most of those events to the same .wav, so they sounded identical.
Listing the actual Media .wav files gives real variety.
"""

from __future__ import annotations

import os
from pathlib import Path

WINDOWS_MEDIA = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Media"


def list_media_sounds() -> dict[str, str]:
    """Return {display_name: wav_path} for .wav files in the Windows Media folder."""
    out: dict[str, str] = {}
    if WINDOWS_MEDIA.exists():
        for f in sorted(WINDOWS_MEDIA.glob("*.wav"), key=lambda p: p.stem.lower()):
            out[f.stem] = str(f)
    return out


def is_wav_path(spec: str) -> bool:
    return bool(spec) and Path(spec).suffix.lower() == ".wav"


def _first_existing(names: list[str]) -> str:
    for n in names:
        p = WINDOWS_MEDIA / n
        if p.exists():
            return str(p)
    sounds = list_media_sounds()
    return next(iter(sounds.values()), "")  # fall back to any media file


def default_success() -> str:
    return _first_existing(
        ["tada.wav", "Windows Notify.wav", "Windows Notify System Generic.wav", "chimes.wav"])


def default_fail() -> str:
    return _first_existing(
        ["Windows Critical Stop.wav", "chord.wav", "Windows Background.wav"])


def play_sound(spec: str) -> None:
    if not spec:
        return
    try:
        import winsound
    except ImportError:
        return  # non-Windows
    try:
        if is_wav_path(spec):
            if Path(spec).exists():
                winsound.PlaySound(spec, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            # Backward-compat: an old saved value may still be a system alias.
            winsound.PlaySound(spec, winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:  # noqa: BLE001  (no audio device, etc.)
        pass
