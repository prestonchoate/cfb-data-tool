# SPDX-License-Identifier: GPL-3.0-or-later
"""Engine orchestrator.

Unlike the original CLI (which captured, extracted, validated, and saved in one
blocking method), the engine here only *produces a result*. It never saves and
never makes noise — the UI decides what to do with a ScanResult (show it, let the
user correct low-confidence fields, then save). This keeps the engine usable
headless (tests) and from a Qt worker thread.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .profiles.base import ScrapeProfile


@dataclass
class ScanResult:
    record: dict                       # field -> value (+ "attributes", "_confidence")
    valid: bool
    missing: list[str] = field(default_factory=list)
    profile_key: str = ""

    @property
    def confidence(self) -> dict:
        return self.record.get("_confidence", {})


class Engine:
    """Capture-agnostic: give it a BGR image, get a ScanResult."""

    def __init__(self, ocr, profile: ScrapeProfile, rois: dict, scale: float = 1.0):
        self.ocr = ocr
        self.profile = profile
        self.rois = rois
        self.scale = scale

    def scan(self, img) -> ScanResult:
        record = self.profile.extract(img, self.rois, self.ocr, scale=self.scale)
        valid, missing = self.profile.validate(record)
        return ScanResult(record=record, valid=valid, missing=missing,
                          profile_key=self.profile.key)
