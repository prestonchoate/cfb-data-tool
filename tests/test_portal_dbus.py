# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for portal D-Bus stream parsing (no live portal required)."""

import pytest

from app.platform.capture.portal_dbus import (
    PortalDBusError,
    _parse_first_stream,
    _parse_size,
)


def test_parse_simple_stream():
    node_id, props = _parse_first_stream([(42, {"size": (1920, 1080)})])
    assert node_id == 42
    assert _parse_size(props) == (1920, 1080)


def test_parse_array_variant_wrapper():
    node_id, props = _parse_first_stream(("a", [(42, {"size": (2560, 1440)})]))
    assert node_id == 42
    assert _parse_size(props) == (2560, 1440)


def test_parse_flat_variant_struct():
    raw = [("a", {"size": ("(ii)", (1920, 1080))}), ("u", 99)]
    node_id, props = _parse_first_stream(raw)
    assert node_id == 99
    assert _parse_size(props) == (1920, 1080)


def test_parse_properties_first_entry():
    raw = [("a", {"size": (1920, 1080)}), ("u", 55)]
    node_id, props = _parse_first_stream(raw)
    assert node_id == 55
    assert _parse_size(props) == (1920, 1080)


def test_parse_nested_variants():
    raw = {
        "streams": ("a(ua{sv})", [(("u", 7), ("a", {"size": ("(ii)", (800, 600))}))]),
    }
    node_id, props = _parse_first_stream(raw["streams"])
    assert node_id == 7
    assert _parse_size(props) == (800, 600)


def test_parse_missing_streams():
    with pytest.raises(PortalDBusError):
        _parse_first_stream(("a", []))


class _FakeFD:
    def __init__(self, fd: int):
        self._fd = fd

    def to_raw_fd(self):
        return self._fd


def test_extract_pipewire_fd():
    from types import SimpleNamespace

    from app.platform.capture.portal_dbus import _extract_pipewire_fd

    reply = SimpleNamespace(body=[_FakeFD(42)])
    assert _extract_pipewire_fd(reply) == 42
