# SPDX-License-Identifier: GPL-3.0-or-later
"""Scrape profiles. Importing this package registers the built-in profiles."""

from .base import PROFILES, ScrapeProfile, get_profile, register_profile
from . import recruits  # noqa: F401  (import for side-effect: registers 'recruits')

__all__ = ["PROFILES", "ScrapeProfile", "get_profile", "register_profile"]
