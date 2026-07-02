# SPDX-License-Identifier: GPL-3.0-or-later
"""Blocking xdg-desktop-portal ScreenCast session for monitor capture."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
SCREEN_CAST_IFACE = "org.freedesktop.portal.ScreenCast"
REQUEST_IFACE = "org.freedesktop.portal.Request"
MONITOR_SOURCE_TYPE = 1


@dataclass
class PortalStreamInfo:
    fd: int
    node_id: int
    width: int
    height: int
    session_handle: str


class PortalDBusError(RuntimeError):
    pass


class PortalDBusSession:
    """Keeps the session-bus connection open for the lifetime of a portal cast."""

    def __init__(self) -> None:
        self._conn = None

    def open_monitor_stream(self) -> PortalStreamInfo:
        DBusAddress, MatchRule, new_method_call, open_dbus_connection = _require_jeepney()
        self.close()
        self._conn = open_dbus_connection(bus="SESSION", enable_fds=True)
        conn = self._conn
        sender = re.sub(r"\.", "_", conn.unique_name[1:])
        session_token = f"cfb_{uuid.uuid4().hex[:8]}"

        create_results = _portal_call(
            conn, MatchRule, new_method_call, DBusAddress, "CreateSession", "a{sv}",
            (_variant_dict({"session_handle_token": session_token}),),
            sender,
        )
        session_handle = create_results.get("session_handle")
        if not session_handle:
            raise PortalDBusError("CreateSession returned no session_handle")

        _portal_call(
            conn, MatchRule, new_method_call, DBusAddress, "SelectSources", "oa{sv}",
            (
                session_handle,
                _variant_dict({
                    "multiple": False,
                    "types": MONITOR_SOURCE_TYPE,
                    "cursor_mode": 2,
                }),
            ),
            sender,
        )

        start_results = _portal_call(
            conn, MatchRule, new_method_call, DBusAddress, "Start", "osa{sv}",
            (session_handle, "", {}),
            sender,
        )
        streams = start_results.get("streams", [])
        if not streams:
            raise PortalDBusError("Start returned no streams")

        stream = streams[0]
        node_id = int(stream[0])
        stream_opts = stream[1] if len(stream) > 1 else {}
        size = stream_opts.get("size", (0, 0))
        width = int(size[0]) if size and size[0] else 0
        height = int(size[1]) if size and size[1] else 0

        portal = DBusAddress(
            PORTAL_PATH,
            bus_name=PORTAL_BUS,
            interface=SCREEN_CAST_IFACE,
        )
        pw_msg = new_method_call(portal, "OpenPipeWireRemote", "oa{sv}", (session_handle, {}))
        pw_reply = conn.send_and_get_reply(pw_msg)
        if not pw_reply.unix_fds:
            raise PortalDBusError("OpenPipeWireRemote returned no file descriptor")
        fd = pw_reply.unix_fds[0]

        return PortalStreamInfo(
            fd=fd,
            node_id=node_id,
            width=width,
            height=height,
            session_handle=session_handle,
        )

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass
            self._conn = None


def _require_jeepney():
    try:
        from jeepney import DBusAddress, MatchRule, new_method_call
        from jeepney.io.blocking import open_dbus_connection
    except ImportError as exc:  # pragma: no cover - import guard
        raise PortalDBusError(
            "jeepney is required for Wayland screen capture. "
            "Install with: pip install cfb-data-tool[linux]"
        ) from exc
    return DBusAddress, MatchRule, new_method_call, open_dbus_connection


def _unwrap(value: Any) -> Any:
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str) and len(value[0]) == 1:
        return _unwrap(value[1])
    if isinstance(value, dict):
        return {k: _unwrap(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_unwrap(v) for v in value]
    return value


def _variant_dict(data: dict[str, Any]) -> dict:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            out[key] = ("s", value)
        elif isinstance(value, bool):
            out[key] = ("b", value)
        elif isinstance(value, int):
            out[key] = ("u", value)
        else:
            out[key] = value
    return out


def _wait_response(conn, MatchRule, request_path: str, timeout: float = 120.0) -> tuple[int, dict]:
    rule = MatchRule(
        type="signal",
        interface=REQUEST_IFACE,
        member="Response",
        path=request_path,
    )
    with conn.filter(rule) as matches:
        msg = conn.recv_until_filtered(matches, timeout=timeout)
    response_code = int(msg.body[0])
    results = _unwrap(msg.body[1]) if len(msg.body) > 1 else {}
    return response_code, results


def _request_path(sender: str, token: str) -> str:
    return f"/org/freedesktop/portal/desktop/request/{sender}/{token}"


def _portal_call(conn, MatchRule, new_method_call, DBusAddress, method: str, signature: str, body: tuple,
                 sender: str, timeout: float = 120.0) -> dict:
    request_token = f"cfb_{uuid.uuid4().hex[:8]}"
    request_path = _request_path(sender, request_token)
    portal = DBusAddress(
        PORTAL_PATH,
        bus_name=PORTAL_BUS,
        interface=SCREEN_CAST_IFACE,
    )
    if body and isinstance(body[-1], dict):
        options = dict(body[-1])
        options["handle_token"] = ("s", request_token)
        body = (*body[:-1], options)

    msg = new_method_call(portal, method, signature, body)
    conn.send(msg)
    code, results = _wait_response(conn, MatchRule, request_path, timeout=timeout)
    if code != 0:
        raise PortalDBusError(f"{method} failed (code {code})")
    return results
