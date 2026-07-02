# SPDX-License-Identifier: GPL-3.0-or-later
"""Screen capture facade — delegates to the platform backend."""

from __future__ import annotations

from ..platform import get_capture_backend


def grab_region(region: dict):
    return get_capture_backend().grab_region(region)


def list_monitors() -> list[dict]:
    return get_capture_backend().list_monitors()


def monitor_region(monitor_number: int) -> dict:
    return get_capture_backend().monitor_region(monitor_number)


def offsets_for_monitor(global_offsets: dict, monitor_number: int) -> dict:
    return get_capture_backend().offsets_for_monitor(global_offsets, monitor_number)


def ensure_session(monitor_number: int) -> bool:
    return get_capture_backend().ensure_session(monitor_number)


def close_session() -> None:
    get_capture_backend().close_session()


def needs_session() -> bool:
    return get_capture_backend().needs_session()
