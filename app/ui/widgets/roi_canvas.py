# SPDX-License-Identifier: GPL-3.0-or-later
"""Interactive ROI editor canvas.

A QGraphicsView whose scene coordinates ARE the captured-image pixels, so each
ROI rectangle's geometry maps directly to ``(y, h, x, w)``. Rectangles are
draggable (move) and resizable (8 handles). Handle/pen sizes are kept at a
constant on-screen size regardless of zoom.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsScene, QGraphicsView,
)

_HANDLES = ("tl", "t", "tr", "r", "br", "b", "bl", "l")
_CURSORS = {
    "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
    "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
    "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
    "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor,
}
_MIN_SIZE = 8.0  # minimum ROI size in image pixels


class RoiItem(QGraphicsRectItem):
    """A movable + resizable labelled rectangle. Geometry is kept in scene
    (image-pixel) coordinates; the item's own pos stays at the origin."""

    def __init__(self, name: str, rect: QRectF, color: QColor, on_change):
        super().__init__(rect)
        self.name = name
        self.color = color
        self._on_change = on_change
        self._drag = None           # active handle key or "body"
        self._start_rect = None
        self._press_pos = None
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setZValue(10)

    # -- geometry helpers --------------------------------------------------
    def geom(self) -> tuple[int, int, int, int]:
        r = self.rect()
        return (round(r.y()), round(r.height()), round(r.x()), round(r.width()))

    def set_geom(self, yhxw):
        y, h, x, w = yhxw
        self.prepareGeometryChange()
        self.setRect(QRectF(x, y, w, h))
        self.update()

    def _scale(self) -> float:
        views = self.scene().views() if self.scene() else []
        return views[0].transform().m11() if views else 1.0

    def _handle_size(self) -> float:
        return 5.0 / max(self._scale(), 1e-6)  # ~5px on screen

    def _handle_rects(self) -> dict:
        r = self.rect()
        hs = self._handle_size()
        cx, cy = r.center().x(), r.center().y()
        pts = {
            "tl": (r.left(), r.top()), "t": (cx, r.top()), "tr": (r.right(), r.top()),
            "r": (r.right(), cy), "br": (r.right(), r.bottom()), "b": (cx, r.bottom()),
            "bl": (r.left(), r.bottom()), "l": (r.left(), cy),
        }
        return {k: QRectF(px - hs, py - hs, 2 * hs, 2 * hs) for k, (px, py) in pts.items()}

    def _handle_at(self, pos: QPointF):
        for key, hr in self._handle_rects().items():
            if hr.contains(pos):
                return key
        return None

    def boundingRect(self) -> QRectF:
        m = self._handle_size() * 2
        return self.rect().adjusted(-m, -m - 16 / max(self._scale(), 1e-6), m, m)

    # -- painting ----------------------------------------------------------
    def paint(self, painter, option, widget=None):
        scale = self._scale()
        r = self.rect()
        selected = self.isSelected()

        pen = QPen(self.color, (2.5 if selected else 1.5) / max(scale, 1e-6))
        painter.setPen(pen)
        if selected:
            fill = QColor(self.color)
            fill.setAlpha(40)
            painter.setBrush(QBrush(fill))
        else:
            painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)

        # Label above the top-left corner.
        font = QFont()
        font.setPointSizeF(max(8.0, 11.0 / max(scale, 1e-6)))
        painter.setFont(font)
        painter.setPen(QPen(self.color))
        painter.drawText(QPointF(r.left(), r.top() - 4 / max(scale, 1e-6)), self.name)

        if selected:
            painter.setBrush(QBrush(self.color))
            painter.setPen(QPen(QColor("white"), 1.0 / max(scale, 1e-6)))
            for hr in self._handle_rects().values():
                painter.drawRect(hr)

    # -- interaction -------------------------------------------------------
    def hoverMoveEvent(self, event):
        key = self._handle_at(event.pos()) if self.isSelected() else None
        self.setCursor(_CURSORS.get(key, Qt.SizeAllCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        # Single-select: clicking a box deselects the others. Overriding the
        # default press handler skipped Qt's exclusive-selection behaviour, so
        # selections accumulated and overlapping handles fought each other.
        if self.scene():
            self.scene().clearSelection()
        self.setSelected(True)
        self._drag = self._handle_at(event.pos()) or "body"
        self._start_rect = QRectF(self.rect())
        self._press_pos = event.scenePos()
        event.accept()

    def mouseMoveEvent(self, event):
        if not self._drag:
            return
        dx = event.scenePos().x() - self._press_pos.x()
        dy = event.scenePos().y() - self._press_pos.y()
        r = QRectF(self._start_rect)

        if self._drag == "body":
            r.translate(dx, dy)
        else:
            left, top, right, bottom = r.left(), r.top(), r.right(), r.bottom()
            if "l" in self._drag:
                left = min(left + dx, right - _MIN_SIZE)
            if "r" in self._drag:
                right = max(right + dx, left + _MIN_SIZE)
            if "t" in self._drag:
                top = min(top + dy, bottom - _MIN_SIZE)
            if "b" in self._drag:
                bottom = max(bottom + dy, top + _MIN_SIZE)
            r = QRectF(QPointF(left, top), QPointF(right, bottom))

        r = self._clamp_to_scene(r)
        self.prepareGeometryChange()
        self.setRect(r)
        if self._on_change:
            self._on_change(self.name, self.geom())

    def mouseReleaseEvent(self, event):
        self._drag = None
        event.accept()

    def _clamp_to_scene(self, r: QRectF) -> QRectF:
        sr = self.scene().sceneRect() if self.scene() else r
        if r.width() > sr.width():
            r.setWidth(sr.width())
        if r.height() > sr.height():
            r.setHeight(sr.height())
        if r.left() < sr.left():
            r.moveLeft(sr.left())
        if r.top() < sr.top():
            r.moveTop(sr.top())
        if r.right() > sr.right():
            r.moveRight(sr.right())
        if r.bottom() > sr.bottom():
            r.moveBottom(sr.bottom())
        return r


# Distinct colours cycled across ROIs for legibility.
_PALETTE = [
    "#ff5252", "#40c4ff", "#69f0ae", "#ffd740", "#e040fb",
    "#ff6e40", "#18ffff", "#b2ff59", "#ffab40", "#7c4dff",
    "#f06292",
]


class RoiCanvas(QGraphicsView):
    roi_changed = Signal(str, tuple)   # (name, (y, h, x, w))
    roi_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(self.renderHints())
        self.setBackgroundBrush(QColor("#1a1a1a"))
        self._bg_item = None
        self._items: dict[str, RoiItem] = {}
        self._scene.selectionChanged.connect(self._on_selection)

    def set_background(self, pixmap):
        # Block selection signals while tearing down the scene so the handler
        # never touches an item whose C++ object was just deleted.
        self._scene.blockSignals(True)
        self._items.clear()
        self._scene.clear()
        self._bg_item = self._scene.addPixmap(pixmap)
        self._bg_item.setZValue(-10)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self._scene.blockSignals(False)
        self._fit()

    def set_rois(self, rois: dict):
        """Replace all ROI rectangles. ``rois`` = {name: (y, h, x, w)}."""
        self._scene.blockSignals(True)
        for name in list(self._items):
            self._scene.removeItem(self._items.pop(name))
        for i, (name, (y, h, x, w)) in enumerate(rois.items()):
            color = QColor(_PALETTE[i % len(_PALETTE)])
            item = RoiItem(name, QRectF(x, y, w, h), color, self._emit_change)
            self._scene.addItem(item)
            self._items[name] = item
        self._scene.blockSignals(False)

    def get_rois(self) -> dict:
        return {name: item.geom() for name, item in self._items.items()}

    def set_roi(self, name: str, geom):
        item = self._items.get(name)
        if item:
            item.set_geom(geom)

    def select_roi(self, name: str):
        item = self._items.get(name)
        if not item:
            return
        self._scene.blockSignals(True)
        for it in self._items.values():
            it.setSelected(it is item)
        self._raise(item)
        self._scene.blockSignals(False)
        self.viewport().update()

    def _raise(self, item):
        """Put the selected box on top so it stays draggable under overlaps."""
        for it in self._items.values():
            try:
                it.setZValue(20 if it is item else 10)
            except RuntimeError:
                pass

    def _emit_change(self, name, geom):
        self.roi_changed.emit(name, geom)

    def _on_selection(self):
        for name, item in list(self._items.items()):
            try:
                selected = item.isSelected()
            except RuntimeError:  # underlying C++ item already deleted
                continue
            if selected:
                self._raise(item)
                self.roi_selected.emit(name)
                return

    def _fit(self):
        if self._bg_item:
            self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()
