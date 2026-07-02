# SPDX-License-Identifier: GPL-3.0-or-later
"""macOS sound playback via afplay."""

from __future__ import annotations

import subprocess
from pathlib import Path

MACOS_SOUNDS = Path("/System/Library/Sounds")


class MacSound:
    def list_media_sounds(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if MACOS_SOUNDS.exists():
            for f in sorted(MACOS_SOUNDS.iterdir(), key=lambda p: p.stem.lower()):
                if f.suffix.lower() in (".aiff", ".wav"):
                    out[f.stem] = str(f)
        return out

    def _first_existing(self, names: list[str]) -> str:
        for n in names:
            p = MACOS_SOUNDS / n
            if p.exists():
                return str(p)
        sounds = self.list_media_sounds()
        return next(iter(sounds.values()), "")

    def default_success(self) -> str:
        return self._first_existing(["Glass.aiff", "Hero.aiff", "Ping.aiff"])

    def default_fail(self) -> str:
        return self._first_existing(["Basso.aiff", "Sosumi.aiff", "Funk.aiff"])

    def play_sound(self, spec: str) -> None:
        if not spec or not Path(spec).exists():
            return
        try:
            subprocess.Popen(
                ["afplay", spec],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:  # noqa: BLE001
            pass
