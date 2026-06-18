# SPDX-License-Identifier: GPL-3.0-or-later
"""Batch accuracy harness (ported).

Runs the engine over a folder of recruit-card screenshots and reports per-image
pass/fail plus a per-field failure breakdown (useful for tuning OCR parity).

Screenshot source (first that exists):
    1. $CFB_SCREENSHOTS environment variable (point at the full corpus)
    2. tests/fixtures/screenshots (the committed sample)

Outputs a JSON report under tests/reports/.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    sys.stdout.reconfigure(encoding="utf-8")  # avoid cp1252 crashes on Windows
except Exception:
    pass

from app.core.calibration import load_preset
from app.core.engine import Engine
from app.core.ocr.rapidocr_engine import RapidOcrEngine
from app.core.profiles.base import get_profile
import app.core.profiles  # noqa: F401  (registers built-in profiles)

logging.basicConfig(level=logging.ERROR)

VALID_EXT = (".png", ".jpg", ".jpeg", ".webp")


def screenshots_dir() -> Path:
    env = os.environ.get("CFB_SCREENSHOTS")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "fixtures" / "screenshots"


def run(base: Path):
    preset = load_preset("cfb26", "recruits")
    engine = Engine(RapidOcrEngine(), get_profile("recruits"), preset["rois"])

    images = [p for p in base.rglob("*") if p.suffix.lower() in VALID_EXT]
    print(f"\n🧪 Accuracy test over {len(images)} images in {base}\n")
    print(f"{'Path':<40} | {'Name':<18} | {'Pos':<4} | {'Att':<3} | {'Star':<4} | {'Status'}")
    print("-" * 100)

    detailed = []
    field_failures = Counter()
    passes = 0

    for path in images:
        img = cv2.imread(str(path))
        if img is None:
            continue
        result = engine.scan(img)
        rec = result.record
        rel = path.relative_to(base).as_posix()

        if result.valid:
            passes += 1
        else:
            for m in result.missing:
                field_failures[m.split("(")[0]] += 1

        status = "✅ PASS" if result.valid else "❌ FAIL"
        disp = (rel[:37] + "..") if len(rel) > 39 else rel
        print(f"{disp:<40} | {rec['NAME'][:18]:<18} | {rec['POSITION'][:4]:<4} | "
              f"{len(rec['attributes']):<3} | {rec['STARS']:<4} | {status}")

        detailed.append({
            "path": rel,
            "record": {k: v for k, v in rec.items() if k != "_confidence"},
            "confidence": rec.get("_confidence", {}),
            "valid": result.valid,
            "missing": result.missing,
        })

    total = len(detailed)
    accuracy = (passes / total * 100) if total else 0.0
    print("-" * 100)
    print(f"SUMMARY: {passes}/{total} passed  ({accuracy:.1f}%)")
    if field_failures:
        print("Field failures: " + ", ".join(f"{k}={v}" for k, v in field_failures.most_common()))
    print()

    _write_report(detailed, accuracy, dict(field_failures))
    return accuracy


def _write_report(detailed, accuracy, field_failures):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(__file__).resolve().parent / "reports"
    out_dir.mkdir(exist_ok=True)
    report = {
        "timestamp": ts,
        "total_accuracy": f"{accuracy:.1f}%",
        "field_failures": field_failures,
        "results": detailed,
    }
    out = out_dir / f"report_{ts}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"📊 Report: {out}")


if __name__ == "__main__":
    base = screenshots_dir()
    if not base.exists():
        print(f"Screenshot folder not found: {base}")
        sys.exit(1)
    run(base)
