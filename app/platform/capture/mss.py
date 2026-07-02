# SPDX-License-Identifier: GPL-3.0-or-later
"""Screen capture via mss (Windows, macOS, and future Linux X11)."""

from __future__ import annotations

import cv2
import mss
import numpy as np


class MssCapture:
    def grab_region(self, region: dict) -> np.ndarray:
        with mss.mss() as sct:
            shot = sct.grab(region)
            return cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)

    def list_monitors(self) -> list[dict]:
        with mss.mss() as sct:
            return [dict(m) for m in sct.monitors]

    def monitor_region(self, monitor_number: int) -> dict:
        with mss.mss() as sct:
            monitors = sct.monitors
            idx = monitor_number if 0 <= monitor_number < len(monitors) else 1
            m = monitors[idx]
            return {"top": m["top"], "left": m["left"], "width": m["width"], "height": m["height"]}

    def offsets_for_monitor(self, global_offsets: dict, monitor_number: int) -> dict:
        with mss.mss() as sct:
            monitors = sct.monitors
            idx = monitor_number if 0 <= monitor_number < len(monitors) else 1
            m = monitors[idx]
            return {
                "top": m["top"] + global_offsets["top"],
                "left": m["left"] + global_offsets["left"],
                "width": global_offsets["width"],
                "height": global_offsets["height"],
            }

    def ensure_session(self, monitor_number: int) -> bool:
        return True

    def close_session(self) -> None:
        pass

    def needs_session(self) -> bool:
        return False
