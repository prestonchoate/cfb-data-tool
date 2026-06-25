# SPDX-License-Identifier: GPL-3.0-or-later
"""Background workers so OCR never blocks the UI thread.

EngineInitWorker builds the (slow) RapidOCR engine once at startup; ScanWorker
runs a single extraction. Results return to the UI via queued signals.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from ..core import profiles  # noqa: F401  (registers built-in profiles)
from ..core.calibration import resolve_calibration
from ..core.engine import Engine
from ..core.profiles.base import get_profile


class EngineInitWorker(QThread):
    """Build the Engine in a background thread.

    On macOS, onnxruntime can deadlock when initialized off the main thread,
    so the caller should create the OcrEngine on the main thread and pass it
    in via *ocr*.
    """
    ready = Signal(object)   # Engine
    failed = Signal(str)

    def __init__(self, settings, ocr=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._ocr = ocr

    def run(self):
        try:
            ocr = self._ocr
            if ocr is None:
                from ..core.ocr.rapidocr_engine import RapidOcrEngine
                ocr = RapidOcrEngine()

            calib = resolve_calibration(
                self.settings.game_version, self.settings.profile,
                self.settings.monitor_number)
            engine = Engine(
                ocr,
                get_profile(self.settings.profile),
                calib["rois"],
                scale=calib.get("cv_scale", 1.0),
            )
            self.ready.emit(engine)
        except Exception as exc:  # noqa: BLE001 — surface any init failure to the UI
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ScanWorker(QThread):
    done = Signal(object)     # ScanResult
    failed = Signal(str)

    def __init__(self, engine: Engine, frame, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.frame = frame

    def run(self):
        try:
            self.done.emit(self.engine.scan(self.frame))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")
