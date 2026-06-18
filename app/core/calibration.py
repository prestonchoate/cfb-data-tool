# SPDX-License-Identifier: GPL-3.0-or-later
"""Calibration: load ROI presets and scale them to the user's resolution.

Presets are JSON keyed by (game_version, profile) and contain the base
``global_offsets`` (the recruit-card crop on screen) plus per-field ``rois``
relative to that crop. ROIs are stored/used as ``(y, h, x, w)`` tuples to match
the original engine's convention.

Auto-calibration: if the user's monitor resolution differs from the preset's
``base_resolution``, linearly scale the global offsets and every ROI as a
starting guess that the visual editor (Phase 3) lets them fine-tune.
"""

from __future__ import annotations

import json
from pathlib import Path

PRESETS_DIR = Path(__file__).resolve().parents[1] / "config" / "presets"


def preset_path(game_version: str, profile: str) -> Path:
    return PRESETS_DIR / game_version / f"{profile}.json"


def load_preset(game_version: str = "cfb26", profile: str = "recruits") -> dict:
    """Load a preset; ROIs are returned as ``{name: (y, h, x, w)}`` tuples."""
    path = preset_path(game_version, profile)
    if not path.exists():
        raise FileNotFoundError(f"No preset for ({game_version}, {profile}) at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["rois"] = {k: tuple(v) for k, v in data["rois"].items()}
    return data


def scale_rois(rois: dict, src_res, dst_res) -> dict:
    """Linearly scale ``(y, h, x, w)`` ROIs from src to dst resolution."""
    sw, sh = src_res
    dw, dh = dst_res
    fx, fy = dw / sw, dh / sh
    scaled = {}
    for name, (y, h, x, w) in rois.items():
        scaled[name] = (round(y * fy), round(h * fy), round(x * fx), round(w * fx))
    return scaled


def scale_offsets(offsets: dict, src_res, dst_res) -> dict:
    sw, sh = src_res
    dw, dh = dst_res
    fx, fy = dw / sw, dh / sh
    return {
        "top": round(offsets["top"] * fy),
        "left": round(offsets["left"] * fx),
        "width": round(offsets["width"] * fx),
        "height": round(offsets["height"] * fy),
    }
