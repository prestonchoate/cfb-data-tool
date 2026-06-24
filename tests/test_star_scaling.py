# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for star-rating template scaling at different resolutions."""

from __future__ import annotations

import numpy as np
import pytest

from app.core.processor import get_star_rating, DEFAULT_STAR_TEMPLATE


def _blank_roi(h: int, w: int):
    """Black BGR image — no stars, but won't crash."""
    return np.zeros((h, w, 3), dtype=np.uint8)


class TestStarRatingScaling:
    """Verify get_star_rating handles various ROI sizes without crashing."""

    def test_roi_smaller_than_template_does_not_crash(self):
        roi = _blank_roi(20, 80)
        result = get_star_rating(roi, scale=1.0)
        assert 0 <= result <= 5

    def test_scaled_template_does_not_crash(self):
        roi = _blank_roi(25, 120)
        result = get_star_rating(roi, scale=0.5)
        assert 0 <= result <= 5

    def test_scale_1_with_normal_roi(self):
        roi = _blank_roi(50, 240)
        result = get_star_rating(roi, scale=1.0)
        assert 0 <= result <= 5

    def test_very_small_scale(self):
        roi = _blank_roi(10, 48)
        result = get_star_rating(roi, scale=0.2)
        assert 0 <= result <= 5

    def test_upscale(self):
        roi = _blank_roi(100, 480)
        result = get_star_rating(roi, scale=2.0)
        assert 0 <= result <= 5
