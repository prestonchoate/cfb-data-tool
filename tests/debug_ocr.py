# SPDX-License-Identifier: GPL-3.0-or-later
"""Dump raw RapidOCR output per ROI for a single screenshot.

Usage:
    python tests/debug_ocr.py path/to/image.png
    python tests/debug_ocr.py            # uses the first fixture it finds

Helps tune extractors by showing exactly how RapidOCR boxes each field
(whole-line vs per-word) versus what EasyOCR used to return.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    sys.stdout.reconfigure(encoding="utf-8")  # avoid cp1252 crashes on Windows
except Exception:
    pass

from app.core.calibration import load_preset
from app.core.ocr.rapidocr_engine import RapidOcrEngine


def _first_fixture() -> str | None:
    root = Path(__file__).resolve().parent / "fixtures" / "screenshots"
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        for p in root.rglob(ext):
            return str(p)
    return None


def main():
    img_path = sys.argv[1] if len(sys.argv) > 1 else _first_fixture()
    if not img_path:
        print("No image given and no fixtures found.")
        return

    print(f"Image: {img_path}")
    img = cv2.imread(img_path)
    if img is None:
        print("Could not read image.")
        return
    print(f"Shape: {img.shape}")

    preset = load_preset("cfb26", "recruits")
    ocr = RapidOcrEngine()

    for name, (y, h, x, w) in preset["rois"].items():
        crop = img[y:y + h, x:x + w]
        results = ocr.readtext(crop, detail=1)
        boxes = [(round(b[0][1]), t, round(c, 2)) for b, t, c in results]
        print(f"\n[{name}] ({len(boxes)} boxes)")
        for top_y, text, conf in boxes:
            print(f"    y={top_y:<5} conf={conf:<5} {text!r}")


if __name__ == "__main__":
    main()
