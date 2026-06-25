# SPDX-License-Identifier: GPL-3.0-or-later
"""ScrapeProfile interface + registry.

A *profile* is a self-contained definition of one thing to capture (recruit card,
roster, player stats, ...). It owns the ROI keys it needs, how to extract a record
from OCR + CV, how to validate that record, and its output schema. Adding a new
data type later means adding a new ScrapeProfile subclass and registering it — no
changes to the engine or UI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

PROFILES: dict[str, "ScrapeProfile"] = {}


def register_profile(cls):
    """Class decorator: instantiate and register a profile by its ``key``."""
    instance = cls()
    PROFILES[instance.key] = instance
    return cls


def get_profile(key: str) -> "ScrapeProfile":
    try:
        return PROFILES[key]
    except KeyError:
        raise KeyError(f"Unknown profile '{key}'. Registered: {sorted(PROFILES)}")


class ScrapeProfile(ABC):
    """Contract every scrape profile implements."""

    #: stable identifier used in presets and settings (e.g. "recruits")
    key: str = ""
    #: human-friendly name shown in the UI
    display_name: str = ""

    @property
    @abstractmethod
    def roi_keys(self) -> list[str]:
        """ROI names this profile reads (must exist in the active preset)."""

    @property
    @abstractmethod
    def schema(self) -> list[str]:
        """Ordered output column headers for CSV/SQLite."""

    @property
    def dedupe_keys(self) -> list[str]:
        """Schema columns that uniquely identify a record (for de-duplication).
        Defaults to the first column; profiles override as needed."""
        return self.schema[:1]

    @abstractmethod
    def extract(self, img, rois: dict, ocr, *, scale: float = 1.0) -> dict:
        """Extract a record (dict of field -> value) from a BGR image.

        ``rois`` maps roi key -> (y, h, x, w) crop relative to ``img``.
        ``scale`` is the resolution ratio (target / base) for scaling CV templates.
        """

    @abstractmethod
    def validate(self, record: dict) -> tuple[bool, list[str]]:
        """Return (is_valid, missing_or_bad_field_names)."""

    @abstractmethod
    def to_row(self, record: dict) -> list:
        """Flatten a record into a row matching ``schema``."""
