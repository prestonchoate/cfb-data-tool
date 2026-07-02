# SPDX-License-Identifier: GPL-3.0-or-later
"""Windows sound playback via winsound."""

from __future__ import annotations

import os
import sys
from pathlib import Path

WINDOWS_MEDIA = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Media"


class WindowsSound:
    def list_media_sounds(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if WINDOWS_MEDIA.exists():
            for f in sorted(WINDOWS_MEDIA.glob("*.wav"), key=lambda p: p.stem.lower()):
                out[f.stem] = str(f)
        return out

    def _first_existing(self, names: list[str]) -> str:
        for n in names:
            p = WINDOWS_MEDIA / n
            if p.exists():
                return str(p)
        sounds = self.list_media_sounds()
        return next(iter(sounds.values()), "")

    def default_success(self) -> str:
        return self._first_existing(
            ["tada.wav", "Windows Notify.wav", "Windows Notify System Generic.wav", "chimes.wav"])

    def default_fail(self) -> str:
        return self._first_existing(
            ["Windows Critical Stop.wav", "chord.wav", "Windows Background.wav"])

    def play_sound(self, spec: str) -> None:
        if not spec or not Path(spec).exists():
            return
        try:
            import winsound
            suffix = Path(spec).suffix.lower()
            if suffix == ".wav":
                winsound.PlaySound(spec, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                winsound.PlaySound(spec, winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:  # noqa: BLE001
            pass
