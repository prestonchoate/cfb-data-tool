# SPDX-License-Identifier: GPL-3.0-or-later
"""RapidOCR (ONNX) backend.

RapidOCR ships its detection/recognition ONNX models inside the wheel, so this
works fully offline after ``pip install`` — no model download, no PyTorch, no GPU.
"""

from __future__ import annotations

import logging

from .base import OcrEngine

logger = logging.getLogger(__name__)


class RapidOcrEngine(OcrEngine):
    name = "rapidocr"

    def __init__(self):
        # Imported lazily so the module can be inspected without the dep present.
        from rapidocr_onnxruntime import RapidOCR

        logger.info("Initializing RapidOCR (ONNX)...")
        self._engine = RapidOCR()

    def readtext(self, img, detail: int = 1):
        # RapidOCR accepts a BGR ndarray and returns (result, elapse).
        # result is a list of [box, text, score] or None when nothing is found.
        result, _ = self._engine(img)
        if not result:
            return []

        if detail == 0:
            return [text for _box, text, _score in result]

        out = []
        for box, text, score in result:
            # Normalize box to a plain list of [x, y] float pairs (top-left first).
            bbox = [[float(pt[0]), float(pt[1])] for pt in box]
            out.append((bbox, text, float(score)))
        return out
