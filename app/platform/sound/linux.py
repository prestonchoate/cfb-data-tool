# SPDX-License-Identifier: GPL-3.0-or-later
"""Linux sound playback via paplay (PipeWire/PulseAudio)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_BUNDLED = Path(__file__).resolve().parents[2] / "resources" / "sounds"
_FREEDESKTOP_DIRS = (
    Path("/usr/share/sounds"),
    Path("/usr/local/share/sounds"),
)


def _data_sound_dirs() -> list[Path]:
    dirs: list[Path] = []
    for entry in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"):
        dirs.append(Path(entry) / "sounds")
    return dirs


def _iter_sound_files() -> list[Path]:
    seen: set[Path] = set()
    roots = [*_FREEDESKTOP_DIRS, *_data_sound_dirs(), _BUNDLED]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for pattern in ("**/*.wav", "**/*.oga", "**/*.ogg"):
            for path in root.glob(pattern):
                if path not in seen:
                    seen.add(path)
                    files.append(path)
    return sorted(files, key=lambda p: p.stem.lower())


class LinuxSound:
    def list_media_sounds(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for path in _iter_sound_files():
            out[path.stem] = str(path)
        return out

    def _bundled(self, name: str) -> str:
        path = _BUNDLED / name
        return str(path) if path.exists() else ""

    def default_success(self) -> str:
        for candidate in ("success.wav", "complete.oga", "bell.oga"):
            bundled = self._bundled(candidate)
            if bundled:
                return bundled
        sounds = self.list_media_sounds()
        for key in ("complete", "bell", "message-new-instant"):
            if key in sounds:
                return sounds[key]
        return next(iter(sounds.values()), "")

    def default_fail(self) -> str:
        for candidate in ("fail.wav", "dialog-error.oga", "suspend-error.oga"):
            bundled = self._bundled(candidate)
            if bundled:
                return bundled
        sounds = self.list_media_sounds()
        for key in ("dialog-error", "suspend-error", "battery-low"):
            if key in sounds:
                return sounds[key]
        return next(iter(sounds.values()), "")

    def play_sound(self, spec: str) -> None:
        if not spec or not Path(spec).exists():
            return
        player = shutil.which("paplay") or shutil.which("aplay")
        if not player:
            return
        try:
            subprocess.Popen(
                [player, spec],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:  # noqa: BLE001
            pass
