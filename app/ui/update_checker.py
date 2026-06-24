# SPDX-License-Identifier: GPL-3.0-or-later
"""Check GitHub Releases for a newer version (runs in a background thread)."""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error

from PySide6.QtCore import QThread, Signal

from .. import __version__

log = logging.getLogger(__name__)

RELEASES_URL = "https://api.github.com/repos/patches822/cfb-data-tool/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in tag.lstrip("vV").split("."))


class UpdateCheckWorker(QThread):
    update_available = Signal(str, str)  # (latest_version, download_url)

    def run(self):
        try:
            req = urllib.request.Request(
                RELEASES_URL,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "CFBDataTool"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            tag = data.get("tag_name", "")
            if not tag:
                return

            if _parse_version(tag) > _parse_version(__version__):
                url = data.get("html_url", "")
                self.update_available.emit(tag.lstrip("vV"), url)
        except Exception:  # noqa: BLE001
            log.debug("Update check failed", exc_info=True)
