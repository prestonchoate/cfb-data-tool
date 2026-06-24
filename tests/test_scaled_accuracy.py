# SPDX-License-Identifier: GPL-3.0-or-later
"""Accuracy harness at simulated resolutions.

Detects the native resolution of whatever fixture screenshots are available,
then resizes them to several standard resolutions and runs the full scan
pipeline at each.  This exercises the template-scaling path in
processor.get_star_rating() and works regardless of the contributor's capture
resolution.

    python tests/test_scaled_accuracy.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app.core.calibration import load_preset, scale_rois
from app.core.engine import Engine
from app.core.ocr.rapidocr_engine import RapidOcrEngine
from app.core.profiles.base import get_profile
import app.core.profiles  # noqa: F401

VALID_EXT = (".png", ".jpg", ".jpeg", ".webp")

# Target monitor resolutions to simulate (width x height).
TARGET_RESOLUTIONS = [
    ("4K",    (3840, 2160)),
    ("1440p", (2560, 1440)),
    ("1080p", (1920, 1080)),
    ("720p",  (1280,  720)),
]


def fixtures_dir() -> Path:
    env = os.environ.get("CFB_SCREENSHOTS")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "fixtures" / "screenshots"


def detect_fixture_scale(sample_path: Path, base_offsets: dict, base_res: tuple) -> float:
    """Derive the monitor-scale of the fixtures from a sample image's dimensions."""
    img = cv2.imread(str(sample_path))
    if img is None:
        return 1.0
    h, w = img.shape[:2]
    fx = w / base_offsets["width"]
    fy = h / base_offsets["height"]
    return min(fx, fy)


def run_at_target(
    images: list[Path],
    base_rois: dict,
    base_res: tuple,
    fixture_scale: float,
    label: str,
    target_res: tuple,
):
    target_scale = min(target_res[0] / base_res[0], target_res[1] / base_res[1])
    resize_factor = target_scale / fixture_scale
    scaled_rois = scale_rois(base_rois, base_res, target_res)

    engine = Engine(RapidOcrEngine(), get_profile("recruits"), scaled_rois, scale=target_scale)

    is_native = abs(resize_factor - 1.0) < 0.01
    native_tag = "  (native — no resize)" if is_native else ""
    print(f"\n{'=' * 80}")
    print(f"  {label} {target_res[0]}x{target_res[1]}  "
          f"(cv_scale={target_scale:.2f}, resize={resize_factor:.2f}x){native_tag}")
    print(f"{'=' * 80}")
    print(f"{'Image':<40} | {'Name':<18} | {'Pos':<4} | {'Att':<3} | {'Star':<4} | {'Status'}")
    print("-" * 90)

    passes = 0
    total = 0

    for path in images:
        img = cv2.imread(str(path))
        if img is None:
            continue

        if is_native:
            scan_img = img
        else:
            new_w = round(img.shape[1] * resize_factor)
            new_h = round(img.shape[0] * resize_factor)
            interp = cv2.INTER_AREA if resize_factor < 1.0 else cv2.INTER_LINEAR
            scan_img = cv2.resize(img, (new_w, new_h), interpolation=interp)

        result = engine.scan(scan_img)
        rec = result.record
        total += 1

        if result.valid:
            passes += 1

        status = "PASS" if result.valid else "FAIL"
        name = path.stem[:18]
        print(f"{name:<40} | {rec['NAME'][:18]:<18} | {rec['POSITION'][:4]:<4} | "
              f"{len(rec['attributes']):<3} | {rec['STARS']:<4} | {status}")

    accuracy = (passes / total * 100) if total else 0.0
    print("-" * 90)
    print(f"  {label}: {passes}/{total} passed ({accuracy:.1f}%)")
    return passes, total


def main() -> int:
    base = fixtures_dir()
    if not base.exists():
        print(f"Screenshot folder not found: {base}")
        return 1

    images = sorted(p for p in base.rglob("*") if p.suffix.lower() in VALID_EXT)
    if not images:
        print(f"No images found in {base}")
        return 1

    preset = load_preset("cfb26", "recruits")
    base_res = tuple(preset["base_resolution"])
    base_rois = preset["rois"]
    base_offsets = preset["global_offsets"]

    fixture_scale = detect_fixture_scale(images[0], base_offsets, base_res)
    sample = cv2.imread(str(images[0]))
    fixture_w, fixture_h = sample.shape[1], sample.shape[0]
    equiv_monitor = (round(base_res[0] * fixture_scale), round(base_res[1] * fixture_scale))

    print(f"Found {len(images)} fixture images.")
    print(f"  Base preset resolution: {base_res[0]}x{base_res[1]}")
    print(f"  Fixture image size:     {fixture_w}x{fixture_h}")
    print(f"  Detected fixture scale: {fixture_scale:.2f}x  "
          f"(equivalent to ~{equiv_monitor[0]}x{equiv_monitor[1]} monitor)")

    overall_pass = 0
    overall_total = 0

    for label, target_res in TARGET_RESOLUTIONS:
        p, t = run_at_target(images, base_rois, base_res, fixture_scale, label, target_res)
        overall_pass += p
        overall_total += t

    print(f"\n{'=' * 80}")
    overall_acc = (overall_pass / overall_total * 100) if overall_total else 0.0
    print(f"  OVERALL: {overall_pass}/{overall_total} ({overall_acc:.1f}%)")
    print(f"{'=' * 80}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
