# SPDX-License-Identifier: GPL-3.0-or-later
"""OCR engine abstraction.

The rest of the engine consumes OCR results in a fixed shape so the underlying
backend (RapidOCR, EasyOCR, ...) can be swapped without touching extractors.

Result shape mirrors EasyOCR's ``readtext`` for an easy port:
- ``detail=0`` -> ``list[str]`` (text only, in reading order)
- ``detail=1`` -> ``list[tuple[bbox, text, conf]]`` where ``bbox`` is a list of
  four ``[x, y]`` corner points (top-left first) and ``conf`` is a float 0..1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

# A bounding box is four [x, y] points; result is (bbox, text, confidence).
BBox = list[list[float]]
OcrResult = tuple[BBox, str, float]


class OcrEngine(ABC):
    """Common interface every OCR backend implements."""

    name: str = "ocr"

    @abstractmethod
    def readtext(self, img, detail: int = 1):
        """Run OCR on a BGR image (numpy array).

        Returns ``list[str]`` when ``detail == 0`` else ``list[OcrResult]``.
        """
        raise NotImplementedError
