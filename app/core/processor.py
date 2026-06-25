# SPDX-License-Identifier: GPL-3.0-or-later
"""Computer-vision helpers that OCR can't handle: star count and gem/bust color.

Ported from the original CLI's ``src/processor.py``. Decoupled from global config
and ``cv2.imshow`` debug windows so it is safe to call headless or from a UI thread.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# app/resources/star_template.png (this file lives in app/core/)
DEFAULT_STAR_TEMPLATE = Path(__file__).resolve().parents[1] / "resources" / "star_template.png"
STAR_MATCH_THRESHOLD = 0.70  # cv2.matchTemplate confidence (TM_CCOEFF_NORMED)


def _deduplicate_star_matches(points, min_distance: int) -> list:
    """Cluster nearby template hits into one point per star (stars are horizontal)."""
    if not points:
        return []

    sorted_points = sorted(points, key=lambda p: p[0])
    groups = [[sorted_points[0]]]
    for point in sorted_points[1:]:
        if point[0] - groups[-1][-1][0] < min_distance:
            groups[-1].append(point)
        else:
            groups.append([point])
    return groups  # one group == one star


def get_star_rating(
    roi_img: np.ndarray,
    template_path: Path | str = DEFAULT_STAR_TEMPLATE,
    scale: float = 1.0,
) -> int:
    """Count stars (1-5) in the star-rating ROI.

    Uses template matching when the star template exists; otherwise falls back to
    contour detection.  *scale* is the resolution ratio (target / base) so the
    template can be resized to match the actual star size in the capture.
    """
    gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
    template_path = Path(template_path)

    use_template = False
    template = None
    if template_path.exists():
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if scale != 1.0:
            new_h = max(1, round(template.shape[0] * scale))
            new_w = max(1, round(template.shape[1] * scale))
            template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)
        if gray.shape[0] < template.shape[0] or gray.shape[1] < template.shape[1]:
            logger.warning(
                "Star ROI (%dx%d) smaller than template (%dx%d) — using contour fallback.",
                gray.shape[1], gray.shape[0], template.shape[1], template.shape[0],
            )
        else:
            use_template = True
    else:
        logger.warning(
            "Star template not found at '%s'. Using contour fallback.", template_path
        )

    if use_template:
        match_result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(match_result >= STAR_MATCH_THRESHOLD)
        hits = list(zip(xs.tolist(), ys.tolist()))
        groups = _deduplicate_star_matches(hits, min_distance=template.shape[1] // 2)
        star_count = len(groups)
    else:
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        star_count = sum(1 for c in contours if 50 < cv2.contourArea(c) < 500)

    return min(star_count, 5)


def detect_gem_status(roi_img: np.ndarray) -> str:
    """Return 'GEM' (green), 'BUST' (red), or 'NORMAL' via HSV color masking."""
    hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)

    green_mask = cv2.inRange(hsv, np.array([40, 40, 40]), np.array([80, 255, 255]))

    # Red wraps around in HSV — check both ends of the hue range.
    red_mask = cv2.bitwise_or(
        cv2.inRange(hsv, np.array([0, 50, 50]), np.array([10, 255, 255])),
        cv2.inRange(hsv, np.array([170, 50, 50]), np.array([180, 255, 255])),
    )

    if cv2.countNonZero(green_mask) > 100:
        return "GEM"
    if cv2.countNonZero(red_mask) > 100:
        return "BUST"
    return "NORMAL"
