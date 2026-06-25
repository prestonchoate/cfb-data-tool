# SPDX-License-Identifier: GPL-3.0-or-later
"""Calibration: load/scale/persist ROI presets for the user's resolution.

Presets are JSON keyed by (game_version, profile). A *bundled* base preset ships
with the app (the 1440p numbers). The user's edits from the visual ROI editor are
saved as *user overrides* in the OS config dir, keyed additionally by resolution,
so different monitors keep their own calibration.

ROIs are ``(y, h, x, w)`` tuples relative to the recruit-card crop
(``global_offsets``), matching the original engine's convention.

resolve_calibration() is the single source of truth used by the engine and UI:
  1. a user override for the active resolution, else
  2. the bundled base preset linearly scaled to the active resolution, else
  3. the bundled base preset as-is.
"""

from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_config_dir

PRESETS_DIR = Path(__file__).resolve().parents[1] / "config" / "presets"
USER_PRESETS_DIR = Path(user_config_dir("cfb-data-tool", appauthor=False)) / "presets"


# ---------------------------------------------------------------------------
# Bundled base presets
# ---------------------------------------------------------------------------
def preset_path(game_version: str, profile: str) -> Path:
    return PRESETS_DIR / game_version / f"{profile}.json"


def load_preset(game_version: str = "cfb26", profile: str = "recruits") -> dict:
    """Load a bundled preset; ROIs returned as ``{name: (y, h, x, w)}`` tuples."""
    path = preset_path(game_version, profile)
    if not path.exists():
        raise FileNotFoundError(f"No preset for ({game_version}, {profile}) at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["rois"] = {k: tuple(v) for k, v in data["rois"].items()}
    return data


# ---------------------------------------------------------------------------
# Scaling
# ---------------------------------------------------------------------------
def scale_rois(rois: dict, src_res, dst_res) -> dict:
    """Linearly scale ``(y, h, x, w)`` ROIs from src to dst resolution."""
    fx, fy = dst_res[0] / src_res[0], dst_res[1] / src_res[1]
    return {
        name: (round(y * fy), round(h * fy), round(x * fx), round(w * fx))
        for name, (y, h, x, w) in rois.items()
    }


def scale_offsets(offsets: dict, src_res, dst_res) -> dict:
    fx, fy = dst_res[0] / src_res[0], dst_res[1] / src_res[1]
    return {
        "top": round(offsets["top"] * fy),
        "left": round(offsets["left"] * fx),
        "width": round(offsets["width"] * fx),
        "height": round(offsets["height"] * fy),
    }


# ---------------------------------------------------------------------------
# User overrides (saved by the visual ROI editor)
# ---------------------------------------------------------------------------
def user_preset_path(game_version: str, profile: str, resolution) -> Path:
    w, h = resolution
    return USER_PRESETS_DIR / game_version / f"{profile}_{w}x{h}.json"


def save_user_calibration(game_version, profile, resolution, global_offsets, rois) -> Path:
    path = user_preset_path(game_version, profile, resolution)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "game_version": game_version,
        "profile": profile,
        "resolution": list(resolution),
        "global_offsets": global_offsets,
        "rois": {k: list(v) for k, v in rois.items()},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_user_calibration(game_version, profile, resolution) -> dict | None:
    path = user_preset_path(game_version, profile, resolution)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data["rois"] = {k: tuple(v) for k, v in data["rois"].items()}
    return data


# ---------------------------------------------------------------------------
# Resolution + resolution
# ---------------------------------------------------------------------------
def detect_resolution(monitor_number: int = 1):
    """Best-effort (width, height) of the given monitor; None if unavailable."""
    try:
        from . import capture
        region = capture.monitor_region(monitor_number)
        return (region["width"], region["height"])
    except Exception:  # noqa: BLE001  (headless / no display)
        return None


def resolve_calibration(game_version: str = "cfb26", profile: str = "recruits",
                        monitor_number: int = 1, resolution=None) -> dict:
    """Return the active calibration as
    ``{"global_offsets", "rois", "resolution", "source"}``.

    ``source`` is "user", "scaled", or "base" for transparency in the UI.
    """
    base = load_preset(game_version, profile)
    base_res = tuple(base["base_resolution"])
    target = tuple(resolution) if resolution else (detect_resolution(monitor_number) or base_res)

    fx, fy = target[0] / base_res[0], target[1] / base_res[1]
    cv_scale = min(fx, fy)

    user = load_user_calibration(game_version, profile, target)
    if user:
        return {
            "global_offsets": user["global_offsets"],
            "rois": user["rois"],
            "resolution": target,
            "cv_scale": cv_scale,
            "source": "user",
        }

    if target != base_res:
        return {
            "global_offsets": scale_offsets(base["global_offsets"], base_res, target),
            "rois": scale_rois(base["rois"], base_res, target),
            "resolution": target,
            "cv_scale": cv_scale,
            "source": "scaled",
        }

    return {
        "global_offsets": base["global_offsets"],
        "rois": base["rois"],
        "resolution": base_res,
        "cv_scale": 1.0,
        "source": "base",
    }
