# SPDX-License-Identifier: GPL-3.0-or-later
"""Wayland screen capture via xdg-desktop-portal monitor screencast."""

from __future__ import annotations

import logging
import threading
import time

import cv2
import numpy as np

from .crop import crop_bgra_to_bgr, scale_factors
from .portal_dbus import PortalDBusError, PortalDBusSession

logger = logging.getLogger(__name__)


def _qt_screens():
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        return []
    return app.screens()


def _screen_geometry(screen) -> dict:
    ratio = screen.devicePixelRatio()
    geo = screen.geometry()
    return {
        "top": int(geo.y() * ratio),
        "left": int(geo.x() * ratio),
        "width": int(geo.width() * ratio),
        "height": int(geo.height() * ratio),
    }


def _monitor_geometries() -> list[dict]:
    return [_screen_geometry(s) for s in _qt_screens()]


class PortalMonitorCapture:
    def __init__(self) -> None:
        self._frame_lock = threading.Lock()
        self._latest_frame: np.ndarray | None = None
        self._stream = None
        self._stream_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._monitor_number = 1
        self._monitor_origin: dict = {"top": 0, "left": 0, "width": 1920, "height": 1080}
        self._session_open = False
        self._portal_info = None
        self._dbus_session: PortalDBusSession | None = None

    def needs_session(self) -> bool:
        return True

    def list_monitors(self) -> list[dict]:
        geometries = _monitor_geometries()
        if not geometries:
            return [{"top": 0, "left": 0, "width": 1920, "height": 1080}]

        min_left = min(g["left"] for g in geometries)
        min_top = min(g["top"] for g in geometries)
        max_right = max(g["left"] + g["width"] for g in geometries)
        max_bottom = max(g["top"] + g["height"] for g in geometries)
        virtual = {
            "top": min_top,
            "left": min_left,
            "width": max_right - min_left,
            "height": max_bottom - min_top,
        }
        return [virtual, *geometries]

    def monitor_region(self, monitor_number: int) -> dict:
        monitors = self.list_monitors()
        idx = monitor_number if 0 <= monitor_number < len(monitors) else 1
        return dict(monitors[idx])

    def offsets_for_monitor(self, global_offsets: dict, monitor_number: int) -> dict:
        m = self.monitor_region(monitor_number)
        return {
            "top": m["top"] + global_offsets["top"],
            "left": m["left"] + global_offsets["left"],
            "width": global_offsets["width"],
            "height": global_offsets["height"],
        }

    def ensure_session(self, monitor_number: int) -> bool:
        if self._session_open and self._monitor_number == monitor_number:
            return True
        self.close_session()
        self._monitor_number = monitor_number
        self._monitor_origin = self.monitor_region(monitor_number)

        try:
            self._dbus_session = PortalDBusSession()
            self._portal_info = self._dbus_session.open_monitor_stream()
        except PortalDBusError as exc:
            logger.warning("Portal screen capture unavailable: %s", exc)
            return False

        try:
            from pipewire_capture import CaptureStream
        except ImportError as exc:
            logger.warning("pipewire-capture is required for Wayland capture: %s", exc)
            return False

        width = self._portal_info.width or self._monitor_origin["width"]
        height = self._portal_info.height or self._monitor_origin["height"]
        self._stream = CaptureStream(
            self._portal_info.fd,
            self._portal_info.node_id,
            width,
            height,
            capture_interval=0.25,
        )
        self._stop_event.clear()
        self._stream.start()
        self._stream_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._stream_thread.start()
        self._session_open = True
        return True

    def _read_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._stream is None:
                break
            if getattr(self._stream, "window_invalid", False):
                logger.warning("Portal capture stream became invalid")
                break
            frame = self._stream.get_frame()
            if frame is not None:
                with self._frame_lock:
                    self._latest_frame = frame
            time.sleep(0.05)

    def grab_region(self, region: dict) -> np.ndarray:
        if not self._session_open:
            raise RuntimeError("Screen capture session not started — call ensure_session first")

        with self._frame_lock:
            frame = None if self._latest_frame is None else self._latest_frame.copy()

        if frame is None:
            raise RuntimeError("No frame available from portal capture stream yet")

        sx, sy = scale_factors(frame.shape, self._monitor_origin)
        return crop_bgra_to_bgr(frame, region, self._monitor_origin, sx, sy)

    def close_session(self) -> None:
        self._stop_event.set()
        if self._stream_thread is not None:
            self._stream_thread.join(timeout=2.0)
            self._stream_thread = None
        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception:  # noqa: BLE001
                pass
            self._stream = None
        self._portal_info = None
        if self._dbus_session is not None:
            self._dbus_session.close()
            self._dbus_session = None
        with self._frame_lock:
            self._latest_frame = None
        self._session_open = False
