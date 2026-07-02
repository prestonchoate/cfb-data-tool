# SPDX-License-Identifier: GPL-3.0-or-later
"""Platform backends selected at runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .capture.protocol import CaptureBackend
    from .hotkey.protocol import HotkeyBackend

_capture_backend: CaptureBackend | None = None
_hotkey_backend: HotkeyBackend | None = None


def get_capture_backend() -> CaptureBackend:
    global _capture_backend
    if _capture_backend is None:
        from .detect import desktop_target
        from .capture.mss import MssCapture

        target = desktop_target()
        if target == "linux_wayland":
            from .capture.portal import PortalMonitorCapture
            _capture_backend = PortalMonitorCapture()
        else:
            _capture_backend = MssCapture()
    return _capture_backend


def get_hotkey_backend() -> HotkeyBackend:
    global _hotkey_backend
    if _hotkey_backend is None:
        from .hotkey.keyboard import KeyboardHotkey
        _hotkey_backend = KeyboardHotkey()
    return _hotkey_backend
