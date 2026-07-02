# SPDX-License-Identifier: GPL-3.0-or-later
"""Platform and display-server detection."""

from __future__ import annotations

import os
import sys
from typing import Literal

DesktopTarget = Literal["windows", "macos", "linux_wayland", "linux_x11"]


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def is_wayland() -> bool:
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return False
    if os.environ.get("QT_QPA_PLATFORM", "").startswith("xcb"):
        return False
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def desktop_target() -> DesktopTarget:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if is_linux():
        if is_wayland():
            return "linux_wayland"
        return "linux_x11"
    return "windows"
