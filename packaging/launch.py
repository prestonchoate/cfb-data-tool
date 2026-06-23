# SPDX-License-Identifier: GPL-3.0-or-later
"""Frozen-app entry point.

app/main.py uses package-relative imports, so it can't be PyInstaller's __main__
directly. This shim imports the package and calls into it.

Set CFB_SMOKE=1 to run a headless self-check (load the bundled preset + OCR
models, then exit) — used to verify a build without opening a window.
"""

import os
import sys


def _smoke() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.core.calibration import load_preset
    from app.core.ocr.rapidocr_engine import RapidOcrEngine

    QApplication([])
    load_preset("cfb26", "recruits")  # bundled preset JSON
    RapidOcrEngine()                  # bundled ONNX models
    msg = "SMOKE OK"
    # Windowed builds have no console, so write the result to a file.
    out = os.environ.get("CFB_SMOKE_OUT", os.path.join(os.path.dirname(sys.executable), "smoke_result.txt"))
    with open(out, "w", encoding="utf-8") as f:
        f.write(msg)
    print(msg)
    return 0


def main():
    if os.environ.get("CFB_SMOKE") == "1":
        sys.exit(_smoke())
    from app.main import main as app_main
    app_main()


if __name__ == "__main__":
    main()
