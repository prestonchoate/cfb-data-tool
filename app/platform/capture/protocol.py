# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture backend protocol."""

from __future__ import annotations

from typing import Protocol

import numpy as np


class CaptureBackend(Protocol):
    def grab_region(self, region: dict) -> np.ndarray:
        """Grab an absolute screen region. ``region`` = {top, left, width, height}."""
        ...

    def list_monitors(self) -> list[dict]:
        """Return per-monitor geometry. Index 0 is virtual bounds; monitors start at 1."""
        ...

    def monitor_region(self, monitor_number: int) -> dict:
        """Full-screen region for a monitor number (1-based)."""
        ...

    def offsets_for_monitor(self, global_offsets: dict, monitor_number: int) -> dict:
        """Translate preset offsets into absolute capture coordinates."""
        ...

    def ensure_session(self, monitor_number: int) -> bool:
        """Prepare capture (portal consent on Wayland). No-op on other platforms."""
        ...

    def close_session(self) -> None:
        """Release capture resources."""
        ...

    def needs_session(self) -> bool:
        """Whether ensure_session must be called before grab_region."""
        ...
