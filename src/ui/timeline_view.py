from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Iterable

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.core.schemas import EventCategory, EventLevel, EventModel
from src.ui.theme import BACKGROUND, BORDER, CATEGORY_COLORS, SURFACE, TEXT, TEXT_DIM, TEXT_MUTED
from src.ui.render_rules import preview_for_event, title_for_event


LANE_ORDER: tuple[EventCategory, ...] = (
    EventCategory.HTTP,
    EventCategory.LLM,
    EventCategory.TOOL,
    EventCategory.FILE,
    EventCategory.PARSER,
    EventCategory.ERROR,
    EventCategory.PERFORMANCE,
    EventCategory.SYSTEM,
    EventCategory.AUTH,
    EventCategory.SESSION,
    EventCategory.CONFIG,
    EventCategory.MCP,
)


class EventCardItem(QGraphicsObject):
    clicked = Signal(str)

    def __init__(self, event_model: EventModel, width: float = 176, height: float = 58, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self.event_model = event_model
        self.width = width
        self.height = height
        self._selected = False
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setToolTip(self._tooltip_text())

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-12, -12, self.width + 24, self.height + 24)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        event = self.event_model
        color = QColor(CATEGORY_COLORS.get(event.category, "#9aa4b2"))
        is_error = event.category == EventCategory.ERROR or event.level == EventLevel.ERROR

        rect = QRectF(0, 0, self.width, self.height)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if self._selected:
            painter.setPen(QPen(QColor("#d9e4ff"), 1.7, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(-7, -7, self.width + 14, self.height + 14), 13, 13)

        painter.setPen(QPen(QColor("#ef4444") if is_error else color, 1.4))
        painter.setBrush(QBrush(QColor("#0d1728")))
        painter.drawRoundedRect(rect, 11, 11)

        # Category stripe/dot.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(QRectF(0, 0, 5, self.height), 3, 3)
        painter.drawEllipse(QRectF(14, 14, 8, 8))

        font = QFont("Segoe UI", 9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(TEXT))
        painter.drawText(QRectF(30, 6, self.width - 40, 21), Qt.AlignLeft | Qt.AlignVCenter, self._elide(title_for_event(event), 38))

        font_sub = QFont("Segoe UI", 8)
        painter.setFont(font_sub)
        painter.setPen(QColor(TEXT_MUTED))
        painter.drawText(QRectF(30, 29, self.width - 40, 19), Qt.AlignLeft | Qt.AlignVCenter, self._elide(self._subtitle(), 44))

        if is_error:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#ef4444")))
            painter.drawEllipse(QRectF(self.width - 22, 9, 14, 14))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(self.width - 22, 8, 14, 14), Qt.AlignCenter, "!")

    def mouseReleaseEvent(self, evt) -> None:
        self.clicked.emit(self.event_model.id)
        super().mouseReleaseEvent(evt)

    def _subtitle(self) -> str:
        event = self.event_model
        rendered = preview_for_event(event, max_chars=72)
        if rendered and rendered not in ("unable to evaluate", "null"):
            return rendered
        details = event.details or {}
        if event.category == EventCategory.HTTP:
            status = details.get("status_code") or details.get("status") or ""
            if event.duration_ms is not None:
                return f"{status} · {event.duration_ms:.0f}ms" if status else f"{event.duration_ms:.0f}ms"
            return str(status or event.type)
        if event.category == EventCategory.LLM:
            if details.get("finish_reason"):
                return f"finish: {details['finish_reason']}"
            tokens = details.get("tokens") or details.get("total_tokens") or details.get("prompt_tokens")
            return f"tokens: {tokens}" if tokens else event.type
        if event.category == EventCategory.TOOL:
            return str(details.get("name") or details.get("tool") or event.type)
        if event.category == EventCategory.FILE:
            return event.refs[0].path if event.refs else "file ref"
        if event.category == EventCategory.PERFORMANCE and event.duration_ms is not None:
            return f"{event.duration_ms:.0f}ms"
        if event.category == EventCategory.ERROR:
            return str(details.get("message") or details.get("error") or event.type)[:42]
        return event.type

    def _tooltip_text(self) -> str:
        event = self.event_model
        return "\n".join([
            event.summary or event.type,
            f"preview: {preview_for_event(event, max_chars=180)}",
            f"category: {event.category.value}",
            f"level: {event.level.value}",
            f"run: {event.run_id or '-'}",
            f"request: {event.request_id or '-'}",
        ])

    @staticmethod
    def _elide(value: str, limit: int) -> str:
        value = str(value)
        return value if len(value) <= limit else value[: max(0, limit - 1)] + "…"


class ConnectorItem(QGraphicsObject):
    def __init__(self, start_pos: QPointF, end_pos: QPointF, *, color: str = "#465674", dashed: bool = False,
                 parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self.start_pos = QPointF(start_pos)
        self.end_pos = QPointF(end_pos)
        self.color = QColor(color)
        self.dashed = dashed
        self.setZValue(-5)

    def boundingRect(self) -> QRectF:
        x_min = min(self.start_pos.x(), self.end_pos.x()) - 70
        x_max = max(self.start_pos.x(), self.end_pos.x()) + 70
        y_min = min(self.start_pos.y(), self.end_pos.y()) - 70
        y_max = max(self.start_pos.y(), self.end_pos.y()) + 70
        return QRectF(x_min, y_min, x_max - x_min, y_max - y_min)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath(self.start_pos)
        mid_x = (self.start_pos.x() + self.end_pos.x()) / 2
        path.cubicTo(mid_x, self.start_pos.y(), mid_x, self.end_pos.y(), self.end_pos.x(), self.end_pos.y())
        painter.setPen(QPen(self.color, 1.25, Qt.DashLine if self.dashed else Qt.SolidLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)


class TimelineScene(QGraphicsScene):
    def __init__(self, lane_y: dict[EventCategory, float], lane_counts: dict[EventCategory, int], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(QColor(BACKGROUND)))
        self._lane_y = lane_y
        self._lane_counts = lane_counts
        self._lane_height = 72.0

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawBackground(painter, rect)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Subtle vertical time grid.
        grid_pen = QPen(QColor("#172033"), 1, Qt.DotLine)
        painter.setPen(grid_pen)
        left = max(140, int(rect.left()) - (int(rect.left()) % 160))
        right = int(rect.right()) + 160
        for x in range(left, right, 160):
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

        font = QFont("Segoe UI", 9)
        font.setBold(True)
        painter.setFont(font)

        for index, (category, y) in enumerate(self._lane_y.items()):
            band = QRectF(0, y - self._lane_height / 2, self.sceneRect().width(), self._lane_height)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#0d1424" if index % 2 == 0 else "#0a1020")))
            painter.drawRect(band)

            color = QColor(CATEGORY_COLORS.get(category, "#9aa4b2"))
            painter.setPen(QPen(color, 1, Qt.DashLine))
            painter.drawLine(QPointF(128, y), QPointF(self.sceneRect().width() - 24, y))

            painter.setPen(color)
            painter.drawText(QRectF(14, y - 17, 92, 20), Qt.AlignLeft | Qt.AlignVCenter, category.value.upper())
            painter.setPen(QColor(TEXT_MUTED))
            painter.drawText(QRectF(92, y - 17, 28, 20), Qt.AlignRight | Qt.AlignVCenter, str(self._lane_counts.get(category, 0)))


class TimelineView(QGraphicsView):
    event_selected = Signal(str)
    zoom_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        self._lane_y: dict[EventCategory, float] = {}
        self._lane_counts: dict[EventCategory, int] = {}
        self._scene = TimelineScene(self._lane_y, self._lane_counts)
        super().__init__(parent)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setBackgroundBrush(QBrush(QColor(BACKGROUND)))
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setInteractive(True)
        self.setCursor(QCursor(Qt.OpenHandCursor))
        self.selected_event_id: str | None = None
        self.items_map: dict[str, EventCardItem] = {}
        self.connectors: list[ConnectorItem] = []
        self._zoom_percent = 100

    def set_zoom_percent(self, percent: int) -> None:
        percent = max(35, min(220, int(percent)))
        if percent == self._zoom_percent:
            return
        self._zoom_percent = percent
        self.resetTransform()
        scale = percent / 100.0
        self.scale(scale, scale)
        self.zoom_changed.emit(percent)

    def zoom_percent(self) -> int:
        return self._zoom_percent

    def zoom_in(self) -> None:
        self.set_zoom_percent(self._zoom_percent + 10)

    def zoom_out(self) -> None:
        self.set_zoom_percent(self._zoom_percent - 10)

    def reset_zoom(self) -> None:
        self.set_zoom_percent(100)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            self.set_zoom_percent(self._zoom_percent + (10 if event.angleDelta().y() > 0 else -10))
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.setCursor(QCursor(Qt.ClosedHandCursor))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.setCursor(QCursor(Qt.OpenHandCursor))

    def set_selected_event(self, event_id: str | None, *, reveal: bool = False) -> None:
        """Mark an event selected. Only scrolls the viewport when ``reveal`` is
        explicitly requested (an explicit user navigation), never as a side
        effect of a rebuild/append — background refreshes must not move the view.
        """
        self.selected_event_id = event_id
        for eid, item in self.items_map.items():
            item.set_selected(eid == event_id)
        if reveal and event_id and event_id in self.items_map:
            self.ensureVisible(self.items_map[event_id], 80, 80)

    def populate_events(self, events: list[EventModel], visual_state: str = "main_desktop_timeline") -> None:
        self.setUpdatesEnabled(False)
        old_scene = self._scene
        try:
            lane_order = self._active_lanes(events)
            self._lane_y = {cat: 88.0 + i * 86.0 for i, cat in enumerate(lane_order)}
            self._lane_counts = {cat: sum(1 for event in events if event.category == cat) for cat in lane_order}
            self._scene = TimelineScene(self._lane_y, self._lane_counts, self)
            self.setScene(self._scene)
            self.items_map = {}
            self.connectors = []
            if old_scene is not None:
                old_scene.deleteLater()

            if not events:
                self._scene.setSceneRect(0, 0, 900, 420)
                return

            positions, widths = self._layout_events(events, lane_order, visual_state)
            max_x = max((x + widths.get(event_id, 176) for event_id, (x, _y) in positions.items()), default=900)
            max_y = max(self._lane_y.values(), default=300) + 72
            self._scene.setSceneRect(0, 0, max(980, max_x + 180), max(420, max_y))

            for event in events:
                x, y = positions[event.id]
                item = EventCardItem(event, width=widths.get(event.id, 176), height=58)
                item.setPos(x, y)
                item.clicked.connect(self._on_card_clicked)
                self._scene.addItem(item)
                self.items_map[event.id] = item

            self._create_connectors(events)
            self.set_selected_event(self.selected_event_id)
        finally:
            self.setUpdatesEnabled(True)
            self.viewport().update()

    def _on_card_clicked(self, event_id: str) -> None:
        self.event_selected.emit(event_id)

    def _active_lanes(self, events: Iterable[EventModel]) -> list[EventCategory]:
        present = {event.category for event in events}
        ordered = [cat for cat in LANE_ORDER if cat in present]
        for cat in sorted(present, key=lambda c: c.value):
            if cat not in ordered:
                ordered.append(cat)
        return ordered or [EventCategory.HTTP, EventCategory.LLM, EventCategory.TOOL, EventCategory.FILE, EventCategory.ERROR]

    def _layout_events(self, events: list[EventModel], lane_order: list[EventCategory], visual_state: str) -> tuple[dict[str, tuple[float, float]], dict[str, float]]:
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        lane_slots: dict[EventCategory, int] = defaultdict(int)
        positions: dict[str, tuple[float, float]] = {}
        widths: dict[str, float] = {}
        min_ts = min(event.timestamp for event in sorted_events)
        max_ts = max(event.timestamp for event in sorted_events)
        total = max(0.001, (max_ts - min_ts).total_seconds())
        dense = visual_state == "timeline_filmstrip_focused" or len(sorted_events) > 80
        px_per_second = max(22.0, min(190.0, 980.0 / total)) if total > 0.001 else 160.0
        base_x = 155.0

        for event in sorted_events:
            lane_y = self._lane_y.get(event.category, 240.0)
            slot = lane_slots[event.category]
            elapsed = (event.timestamp - min_ts).total_seconds()
            x = base_x + elapsed * px_per_second

            # Enforce minimum spacing inside a lane so same-timestamp events become a filmstrip.
            min_x = base_x + slot * (132 if dense else 190)
            x = max(x, min_x)
            lane_slots[event.category] += 1

            width = self._card_width(event, dense)
            widths[event.id] = width
            y_offset = self._lane_offset(event)
            positions[event.id] = (x, lane_y - 29.0 + y_offset)

        return positions, widths

    def _lane_offset(self, event: EventModel) -> float:
        hay = f"{event.type} {event.summary}".casefold()
        if any(word in hay for word in ("response", "received", "result")):
            return 10.0
        if any(word in hay for word in ("request", "send", "call")):
            return -10.0
        return 0.0

    def _card_width(self, event: EventModel, dense: bool) -> float:
        if dense:
            return 134.0 if event.category in (EventCategory.HTTP, EventCategory.FILE) else 158.0
        text_len = len(event.summary or event.type)
        return max(128.0, min(238.0, 118.0 + text_len * 4.0))

    def _create_connectors(self, events: list[EventModel]) -> None:
        # Explicit parent/child links.
        for event in events:
            if event.parent_event_id and event.parent_event_id in self.items_map and event.id in self.items_map:
                self._add_connector(event.parent_event_id, event.id, dashed=False)

        # Inferred run/request flow links, so the graph still has connections when parent ids are absent.
        grouped: dict[tuple[str | None, str | None], list[EventModel]] = defaultdict(list)
        for event in events:
            key = (event.run_id, event.request_id)
            if any(key):
                grouped[key].append(event)
        linked = {(e.parent_event_id, e.id) for e in events if e.parent_event_id}
        for chain in grouped.values():
            chain = sorted(chain, key=lambda e: e.timestamp)
            for prev, cur in zip(chain, chain[1:]):
                if (prev.id, cur.id) not in linked and prev.id in self.items_map and cur.id in self.items_map:
                    self._add_connector(prev.id, cur.id, dashed=True)

    def _add_connector(self, from_id: str, to_id: str, *, dashed: bool) -> None:
        start_item = self.items_map[from_id]
        end_item = self.items_map[to_id]
        start = start_item.pos() + QPointF(start_item.width, start_item.height / 2)
        end = end_item.pos() + QPointF(0, end_item.height / 2)
        color = CATEGORY_COLORS.get(end_item.event_model.category, "#465674")
        connector = ConnectorItem(start, end, color=color, dashed=dashed)
        self._scene.addItem(connector)
        self.connectors.append(connector)
