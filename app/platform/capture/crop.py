# SPDX-License-Identifier: GPL-3.0-or-later
"""Crop an absolute screen region from a monitor-local BGRA frame."""

from __future__ import annotations

import cv2
import numpy as np


def crop_bgra_to_bgr(
    frame: np.ndarray,
    region: dict,
    monitor_origin: dict,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> np.ndarray:
    """Crop ``region`` (absolute desktop coords) from a monitor-local BGRA frame.

    ``monitor_origin`` is the monitor's top-left in absolute desktop coordinates.
    ``scale_*`` maps desktop pixels to frame pixels when the stream resolution
    differs from Qt-reported geometry (HiDPI).
    """
    rel_top = int((region["top"] - monitor_origin["top"]) * scale_y)
    rel_left = int((region["left"] - monitor_origin["left"]) * scale_x)
    height = max(1, int(region["height"] * scale_y))
    width = max(1, int(region["width"] * scale_x))

    fh, fw = frame.shape[:2]
    rel_top = max(0, min(rel_top, fh - 1))
    rel_left = max(0, min(rel_left, fw - 1))
    height = min(height, fh - rel_top)
    width = min(width, fw - rel_left)

    crop = frame[rel_top : rel_top + height, rel_left : rel_left + width]
    return cv2.cvtColor(crop, cv2.COLOR_BGRA2BGR)


def scale_factors(frame_shape: tuple[int, ...], monitor_geometry: dict) -> tuple[float, float]:
    fh, fw = frame_shape[:2]
    expected_h = max(1, monitor_geometry["height"])
    expected_w = max(1, monitor_geometry["width"])
    return fw / expected_w, fh / expected_h
