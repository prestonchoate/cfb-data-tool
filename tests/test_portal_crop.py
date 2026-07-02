# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for portal frame cropping (no D-Bus required)."""

import numpy as np

from app.platform.capture.crop import crop_bgra_to_bgr, scale_factors


def test_crop_bgra_to_bgr_basic():
    frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
    frame[100:200, 300:500, :] = (0, 255, 0, 255)  # green patch

    region = {"top": 100, "left": 300, "width": 200, "height": 100}
    monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}

    out = crop_bgra_to_bgr(frame, region, monitor)
    assert out.shape == (100, 200, 3)
    assert out[0, 0, 1] == 255  # green channel


def test_crop_with_monitor_offset():
    frame = np.full((900, 1600, 4), (0, 0, 255, 255), dtype=np.uint8)  # red in BGRA
    region = {"top": 110, "left": 210, "width": 50, "height": 40}
    monitor = {"top": 100, "left": 200, "width": 1600, "height": 900}

    out = crop_bgra_to_bgr(frame, region, monitor)
    assert out.shape == (40, 50, 3)
    assert out[0, 0, 2] == 255  # red in BGR


def test_crop_clamps_to_frame_bounds():
    frame = np.zeros((100, 100, 4), dtype=np.uint8)
    region = {"top": 0, "left": 0, "width": 500, "height": 500}
    monitor = {"top": 0, "left": 0, "width": 100, "height": 100}

    out = crop_bgra_to_bgr(frame, region, monitor)
    assert out.shape == (100, 100, 3)


def test_scale_factors():
    frame = np.zeros((2160, 3840, 4), dtype=np.uint8)
    monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
    sx, sy = scale_factors(frame.shape, monitor)
    assert sx == 2.0
    assert sy == 2.0
