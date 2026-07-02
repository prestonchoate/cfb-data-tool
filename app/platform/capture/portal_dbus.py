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
        node_id, stream_opts = _parse_first_stream(start_results.get("streams"))
        size = _parse_size(stream_opts)
        width, height = size

        portal = DBusAddress(
            PORTAL_PATH,
            bus_name=PORTAL_BUS,
            interface=SCREEN_CAST_IFACE,
        )
        pw_msg = new_method_call(portal, "OpenPipeWireRemote", "oa{sv}", (session_handle, {}))
        pw_reply = conn.send_and_get_reply(pw_msg)
        fd = _extract_pipewire_fd(pw_reply)

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


def _extract_pipewire_fd(reply: Any) -> int:
    """Return the PipeWire socket fd from an OpenPipeWireRemote reply."""
    if not reply.body:
        raise PortalDBusError("OpenPipeWireRemote returned no file descriptor")
    fd_obj = reply.body[0]
    if hasattr(fd_obj, "to_raw_fd"):
        return int(fd_obj.to_raw_fd())
    if hasattr(fd_obj, "fileno"):
        return int(fd_obj.fileno())
    if isinstance(fd_obj, int):
        return fd_obj
    raise PortalDBusError(f"OpenPipeWireRemote returned unexpected fd type: {type(fd_obj)!r}")


def _unwrap(value: Any) -> Any:
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
        sig, payload = value
        # D-Bus variant or typed value: (signature, payload)
        if len(sig) == 1 or sig.startswith(("a", "(")):
            return _unwrap(payload)
    if isinstance(value, dict):
        return {k: _unwrap(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_unwrap(v) for v in value]
    return value


def _as_int(value: Any) -> int | None:
    value = _unwrap(value)
    if isinstance(value, int):
        return value
    return None


def _as_dict(value: Any) -> dict:
    value = _unwrap(value)
    return value if isinstance(value, dict) else {}


def _parse_size(props: dict) -> tuple[int, int]:
    size = _unwrap(props.get("size", (0, 0)))
    if isinstance(size, (list, tuple)) and len(size) >= 2:
        w = _as_int(size[0])
        h = _as_int(size[1])
        return (w or 0, h or 0)
    return 0, 0


def _parse_stream_entry(entry: Any, siblings: list[Any] | None = None) -> tuple[int, dict]:
    entry = _unwrap(entry)

    if isinstance(entry, dict):
        props = entry
        if siblings:
            for sibling in siblings:
                sibling = _unwrap(sibling)
                if isinstance(sibling, int):
                    return sibling, props
                if isinstance(sibling, tuple) and len(sibling) == 2 and sibling[0] == "u":
                    node_id = _as_int(sibling[1])
                    if node_id is not None:
                        return node_id, props
        for key in ("pipewire-node", "node_id", "handle"):
            if key in props:
                node_id = _as_int(props[key])
                if node_id is not None:
                    return node_id, props

    if isinstance(entry, (list, tuple)):
        if len(entry) >= 2 and not isinstance(entry[0], str):
            node_id = _as_int(entry[0])
            if node_id is not None:
                return node_id, _as_dict(entry[1])

        # Flat variant struct: [('u', id), ('a', props)] or [('a', props), ('u', id)]
        node_id = None
        props: dict = {}
        for item in entry:
            item = _unwrap(item)
            if isinstance(item, int):
                node_id = item
            elif isinstance(item, dict):
                props = item
            elif isinstance(item, tuple) and len(item) == 2:
                tag, payload = item
                if tag == "u":
                    node_id = _as_int(payload)
                elif tag == "a" and isinstance(_unwrap(payload), dict):
                    props = _as_dict(payload)
        if node_id is not None:
            return node_id, props

        # Properties-only variant: ('a', {...})
        if len(entry) == 2 and entry[0] == "a":
            props = _as_dict(entry[1])
            if siblings:
                for sibling in siblings:
                    sibling = _unwrap(sibling)
                    if isinstance(sibling, tuple) and len(sibling) == 2 and sibling[0] == "u":
                        node_id = _as_int(sibling[1])
                        if node_id is not None:
                            return node_id, props
            for key in ("pipewire-node", "node_id", "handle"):
                if key in props:
                    node_id = _as_int(props[key])
                    if node_id is not None:
                        return node_id, props

    if isinstance(entry, int):
        return entry, {}

    raise PortalDBusError(f"Unrecognized stream entry: {entry!r}")


def _parse_first_stream(raw: Any) -> tuple[int, dict]:
    streams = _unwrap(raw)
    while isinstance(streams, tuple) and len(streams) == 2 and isinstance(streams[0], str):
        if streams[0].startswith("a"):
            streams = streams[1]
        else:
            break
    streams = _unwrap(streams)

    if isinstance(streams, tuple) and len(streams) == 2 and isinstance(streams[0], int):
        streams = [streams]

    if not isinstance(streams, list) or not streams:
        raise PortalDBusError(f"Start returned no streams: {raw!r}")

    # Some compositors flatten one stream into the top-level list.
    if len(streams) >= 2 and all(isinstance(_unwrap(item), tuple) for item in streams[:2]):
        tags = [_unwrap(item)[0] for item in streams[:2] if isinstance(_unwrap(item), tuple)]
        if tags == ["a", "u"] or tags == ["u", "a"]:
            return _parse_stream_entry(streams)

    return _parse_stream_entry(streams[0], siblings=streams[1:])


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
