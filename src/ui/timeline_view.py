from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Iterable

from PySide6.QtCore import QEasingCurve, QObject, QPointF, QPropertyAnimation, QRectF, Qt, Signal
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
        # Compute display text ONCE. title_for_event / preview_for_event run the
        # render-rule engine and expand JSON payloads, which must never happen
        # inside paint() (called many times per card on scroll/zoom).
        self._title_text = title_for_event(event_model)
        self._subtitle_text = self._compute_subtitle()
        self.setToolTip(self._compute_tooltip())

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.update()

    def invalidate_text(self) -> None:
        """Recompute cached display text (e.g. after a render-rule change)."""
        self._title_text = title_for_event(self.event_model)
        self._subtitle_text = self._compute_subtitle()
        self.setToolTip(self._compute_tooltip())
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
        painter.drawText(QRectF(30, 6, self.width - 40, 21), Qt.AlignLeft | Qt.AlignVCenter, self._elide(self._title_text, 38))

        font_sub = QFont("Segoe UI", 8)
        painter.setFont(font_sub)
        painter.setPen(QColor(TEXT_MUTED))
        painter.drawText(QRectF(30, 29, self.width - 40, 19), Qt.AlignLeft | Qt.AlignVCenter, self._elide(self._subtitle_text, 44))

        if is_error:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#ef4444")))
            painter.drawEllipse(QRectF(self.width - 22, 9, 14, 14))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(self.width - 22, 8, 14, 14), Qt.AlignCenter, "!")

    def mouseReleaseEvent(self, evt) -> None:
        self.clicked.emit(self.event_model.id)
        super().mouseReleaseEvent(evt)

    def _compute_subtitle(self) -> str:
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

    def _compute_tooltip(self) -> str:
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


class CollectionCardItem(QGraphicsObject):
    """A single card standing in for a dense burst of same-lane events.

    Renders a stacked-paper motif with a count badge, a category-mix chip row,
    and error precedence (any error in the group shows red). Clicking it asks
    the view to fan the group out into individual cards.
    """

    clicked = Signal(str)

    def __init__(self, group_id: str, events: list[EventModel], width: float = 184.0,
                 height: float = 58.0, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self.group_id = group_id
        self.events = events
        self.width = width
        self.height = height
        self.category = events[0].category
        self.count = len(events)
        self.has_error = any(
            e.category == EventCategory.ERROR or e.level == EventLevel.ERROR for e in events
        )
        self._chip_categories: list[EventCategory] = []
        for e in events:
            if e.category not in self._chip_categories:
                self._chip_categories.append(e.category)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setToolTip(f"{self.count} {self.category.value} events — click to expand")

    def boundingRect(self) -> QRectF:
        return QRectF(-12, -16, self.width + 24, self.height + 30)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        color = QColor(CATEGORY_COLORS.get(self.category, "#9aa4b2"))
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Stacked-paper ghosts behind the front card.
        for off, shade in ((8.0, "#0a1322"), (4.0, "#0b1526")):
            painter.setPen(QPen(QColor(BORDER), 1.0))
            painter.setBrush(QBrush(QColor(shade)))
            painter.drawRoundedRect(QRectF(off, -off, self.width, self.height), 11, 11)

        edge = QColor("#ef4444") if self.has_error else color
        painter.setPen(QPen(edge, 1.4))
        painter.setBrush(QBrush(QColor("#0d1728")))
        painter.drawRoundedRect(QRectF(0, 0, self.width, self.height), 11, 11)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(QRectF(0, 0, 5, self.height), 3, 3)
        painter.drawEllipse(QRectF(14, 12, 8, 8))

        font = QFont("Segoe UI", 9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(TEXT))
        painter.drawText(QRectF(30, 5, self.width - 78, 20), Qt.AlignLeft | Qt.AlignVCenter,
                         f"{self.category.value} group")

        # Count badge, top-right.
        badge_w = 38.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#1b2940")))
        painter.drawRoundedRect(QRectF(self.width - badge_w - 8, 7, badge_w, 16), 8, 8)
        painter.setPen(QColor(TEXT))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(self.width - badge_w - 8, 7, badge_w, 16), Qt.AlignCenter, f"+{self.count}")

        # Category-mix chip row along the bottom.
        painter.setPen(Qt.NoPen)
        cx = 30.0
        for c in self._chip_categories[:6]:
            painter.setBrush(QBrush(QColor(CATEGORY_COLORS.get(c, "#9aa4b2"))))
            painter.drawEllipse(QRectF(cx, self.height - 15, 7, 7))
            cx += 11.0

        painter.setPen(QColor(TEXT_DIM))
        painter.setFont(QFont("Segoe UI", 7))
        painter.drawText(QRectF(30, self.height - 17, self.width - 40, 12),
                         Qt.AlignRight | Qt.AlignVCenter, "click to expand")

        if self.has_error:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#ef4444")))
            painter.drawEllipse(QRectF(self.width - 16, self.height - 16, 9, 9))

    def mouseReleaseEvent(self, evt) -> None:
        self.clicked.emit(self.group_id)
        super().mouseReleaseEvent(evt)


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

    # A same-lane run of >= COLLAPSE_MIN consecutive events collapses into a
    # single collection card (until the user expands it).
    COLLAPSE_MIN = 5
    COLLECTION_WIDTH = 184.0

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
        # "fit" = collision-aware/gap-compressed (default, readable at volume);
        # "time" = raw wall-clock spacing.
        self._axis_mode = "fit"
        # Collection-card (burst collapse) state.
        self._expanded_groups: set[str] = set()
        self.collection_items: dict[str, CollectionCardItem] = {}
        self._member_group: dict[str, str] = {}
        self._last_events: list[EventModel] = []
        self._last_visual_state = "main_desktop_timeline"
        self._fanout_anims: list = []
        self._pending_fanout: tuple[str, float] | None = None

    def set_axis_mode(self, mode: str) -> None:
        if mode not in ("fit", "time") or mode == self._axis_mode:
            return
        self._axis_mode = mode

    def axis_mode(self) -> str:
        return self._axis_mode

    def fit_to_events(self) -> None:
        """Zoom/scroll so every event card is visible at once."""
        if not self.items_map:
            return
        rect = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            return
        self.fitInView(rect.adjusted(-40, -40, 40, 40), Qt.KeepAspectRatio)
        # Reflect the resulting scale back into the zoom indicator.
        scale = self.transform().m11()
        self._zoom_percent = max(35, min(220, int(round(scale * 100))))
        self.zoom_changed.emit(self._zoom_percent)

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
            self._last_events = list(events)
            self._last_visual_state = visual_state
            lane_order = self._active_lanes(events)
            self._lane_y = {cat: 88.0 + i * 86.0 for i, cat in enumerate(lane_order)}
            self._lane_counts = {cat: sum(1 for event in events if event.category == cat) for cat in lane_order}
            self._scene = TimelineScene(self._lane_y, self._lane_counts, self)
            self.setScene(self._scene)
            self.items_map = {}
            self.collection_items = {}
            self._member_group = {}
            self.connectors = []
            if old_scene is not None:
                old_scene.deleteLater()

            if not events:
                self._scene.setSceneRect(0, 0, 900, 420)
                return

            sorted_events = sorted(events, key=lambda e: e.timestamp)
            dense = visual_state == "timeline_filmstrip_focused" or len(sorted_events) > 80
            if getattr(self, "_axis_mode", "fit") == "time":
                units: list[tuple[str, object]] = [("event", e) for e in sorted_events]
            else:
                units = self._build_units(sorted_events)

            # Lay out one column per unit (event card or collection card).
            pack_items: list[dict] = []
            for kind, payload in units:
                if kind == "event":
                    e = payload  # type: ignore[assignment]
                    pack_items.append({"key": ("e", e.id), "category": e.category,
                                       "width": self._card_width(e, dense), "ts": e.timestamp})
                else:
                    run = payload  # type: ignore[assignment]
                    pack_items.append({"key": ("g", self._group_id(run)), "category": run[0].category,
                                       "width": self.COLLECTION_WIDTH, "ts": run[0].timestamp})
            xs = self._pack(pack_items, dense)

            max_x = max((xs[it["key"]] + it["width"] for it in pack_items), default=900)
            max_y = max(self._lane_y.values(), default=300) + 72
            self._scene.setSceneRect(0, 0, max(980, max_x + 180), max(420, max_y))

            for kind, payload in units:
                if kind == "event":
                    e = payload  # type: ignore[assignment]
                    lane_y = self._lane_y.get(e.category, 240.0)
                    item = EventCardItem(e, width=self._card_width(e, dense), height=58)
                    item.setPos(xs[("e", e.id)], lane_y - 29.0 + self._lane_offset(e))
                    item.clicked.connect(self._on_card_clicked)
                    self._scene.addItem(item)
                    self.items_map[e.id] = item
                else:
                    run = payload  # type: ignore[assignment]
                    gid = self._group_id(run)
                    lane_y = self._lane_y.get(run[0].category, 240.0)
                    col = CollectionCardItem(gid, run, width=self.COLLECTION_WIDTH, height=58)
                    col.setPos(xs[("g", gid)], lane_y - 29.0)
                    col.clicked.connect(self._on_collection_clicked)
                    self._scene.addItem(col)
                    self.collection_items[gid] = col
                    for e in run:
                        self._member_group[e.id] = gid

            self._create_connectors(events)
            self.set_selected_event(self.selected_event_id)
            self._run_pending_fanout()
        finally:
            self.setUpdatesEnabled(True)
            self.viewport().update()

    def _on_card_clicked(self, event_id: str) -> None:
        self.event_selected.emit(event_id)

    def _on_collection_clicked(self, group_id: str) -> None:
        """Expand a collapsed burst into its individual cards (with a fan-out)."""
        col = self.collection_items.get(group_id)
        anchor_x = col.pos().x() if col is not None else 155.0
        member_ids = [e.id for e in col.events] if col is not None else []
        self._expanded_groups.add(group_id)
        self._pending_fanout = (group_id, anchor_x, member_ids)
        self.populate_events(self._last_events, self._last_visual_state)

    def collapse_all_groups(self) -> None:
        """Re-collapse every expanded burst."""
        if not self._expanded_groups:
            return
        self._expanded_groups.clear()
        self.populate_events(self._last_events, self._last_visual_state)

    def _run_pending_fanout(self) -> None:
        pending = self._pending_fanout
        self._pending_fanout = None
        if not pending:
            return
        _gid, anchor_x, member_ids = pending
        self._fanout_anims = []
        for eid in member_ids:
            item = self.items_map.get(eid)
            if item is None:
                continue
            target = QPointF(item.pos())
            item.setOpacity(0.0)
            item.setPos(anchor_x, target.y())
            pos_anim = QPropertyAnimation(item, b"pos", self)
            pos_anim.setDuration(200)
            pos_anim.setStartValue(QPointF(anchor_x, target.y()))
            pos_anim.setEndValue(target)
            pos_anim.setEasingCurve(QEasingCurve.OutCubic)
            op_anim = QPropertyAnimation(item, b"opacity", self)
            op_anim.setDuration(180)
            op_anim.setStartValue(0.0)
            op_anim.setEndValue(1.0)
            pos_anim.start()
            op_anim.start()
            self._fanout_anims.append(pos_anim)
            self._fanout_anims.append(op_anim)

    def _active_lanes(self, events: Iterable[EventModel]) -> list[EventCategory]:
        present = {event.category for event in events}
        ordered = [cat for cat in LANE_ORDER if cat in present]
        for cat in sorted(present, key=lambda c: c.value):
            if cat not in ordered:
                ordered.append(cat)
        return ordered or [EventCategory.HTTP, EventCategory.LLM, EventCategory.TOOL, EventCategory.FILE, EventCategory.ERROR]

    def _layout_events(self, events: list[EventModel], lane_order: list[EventCategory], visual_state: str) -> tuple[dict[str, tuple[float, float]], dict[str, float]]:
        """Collision-aware, gap-compressed timeline layout (the "fit" axis).

        Cards are placed left-to-right in chronological order with a global
        cursor that (a) never lets two cards in the same lane overlap and
        (b) caps idle gaps, so dense bursts stay readable and quiet periods
        don't blow the canvas into a sparse void. The scan is prefix-stable:
        an event's position depends only on the events before it, so appending
        new events never shifts existing ones. Real timestamps live in the
        tooltip/inspector. ``self._axis_mode == 'time'`` restores raw
        wall-clock spacing.
        """
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        dense = visual_state == "timeline_filmstrip_focused" or len(sorted_events) > 80
        base_x = 155.0

        if getattr(self, "_axis_mode", "fit") == "time":
            return self._layout_events_time(sorted_events, dense, base_x)

        widths: dict[str, float] = {event.id: self._card_width(event, dense) for event in sorted_events}
        items = [
            {"key": event.id, "category": event.category, "width": widths[event.id], "ts": event.timestamp}
            for event in sorted_events
        ]
        xs = self._pack(items, dense, base_x)
        positions: dict[str, tuple[float, float]] = {}
        for event in sorted_events:
            lane_y = self._lane_y.get(event.category, 240.0)
            positions[event.id] = (xs[event.id], lane_y - 29.0 + self._lane_offset(event))
        return positions, widths

    def _pack(self, items: list[dict], dense: bool, base_x: float = 155.0) -> dict:
        """Place a chronological sequence of items (each a dict with key /
        category / width / ts) left-to-right with collision-aware, gap-
        compressed spacing. Returns {key: x}. Shared by event and collection
        (unit) layout so both stay consistent and prefix-stable.
        """
        min_step = 132.0 if dense else 168.0
        max_gap = 240.0 if dense else 300.0
        px_per_second = 26.0
        lane_gap = 18.0
        xs: dict = {}
        cursor_x = base_x
        lane_right: dict[EventCategory, float] = {}
        prev_ts: datetime | None = None
        for it in items:
            ts = it["ts"]
            if prev_ts is not None:
                cursor_x += max(min_step, min(max_gap, (ts - prev_ts).total_seconds() * px_per_second))
            prev_ts = ts
            x = cursor_x
            cat = it["category"]
            right = lane_right.get(cat)
            if right is not None and x < right + lane_gap:
                x = right + lane_gap
                cursor_x = x  # keep the global cursor monotonic past the bump
            lane_right[cat] = x + it["width"]
            xs[it["key"]] = x
        return xs

    def _group_id(self, run: list[EventModel]) -> str:
        return f"grp_{run[0].id}_{len(run)}"

    def _build_units(self, sorted_events: list[EventModel]) -> list[tuple[str, object]]:
        """Collapse same-lane bursts into groups. Returns a chronological list
        of units: ("event", EventModel) or ("group", list[EventModel]). A run
        of >= COLLAPSE_MIN consecutive same-category events becomes a group,
        unless the user has explicitly expanded it.
        """
        units: list[tuple[str, object]] = []
        i = 0
        n = len(sorted_events)
        while i < n:
            cat = sorted_events[i].category
            j = i + 1
            while j < n and sorted_events[j].category == cat:
                j += 1
            run = sorted_events[i:j]
            if len(run) >= self.COLLAPSE_MIN and self._group_id(run) not in self._expanded_groups:
                units.append(("group", run))
            else:
                units.extend(("event", e) for e in run)
            i = j
        return units

    def _layout_events_time(self, sorted_events: list[EventModel], dense: bool, base_x: float) -> tuple[dict[str, tuple[float, float]], dict[str, float]]:
        """Legacy raw wall-clock layout (``axis_mode == 'time'``)."""
        lane_slots: dict[EventCategory, int] = defaultdict(int)
        positions: dict[str, tuple[float, float]] = {}
        widths: dict[str, float] = {}
        min_ts = min(event.timestamp for event in sorted_events)
        max_ts = max(event.timestamp for event in sorted_events)
        total = max(0.001, (max_ts - min_ts).total_seconds())
        px_per_second = max(22.0, min(190.0, 980.0 / total)) if total > 0.001 else 160.0

        for event in sorted_events:
            lane_y = self._lane_y.get(event.category, 240.0)
            slot = lane_slots[event.category]
            elapsed = (event.timestamp - min_ts).total_seconds()
            x = base_x + elapsed * px_per_second
            min_x = base_x + slot * (132 if dense else 190)
            x = max(x, min_x)
            lane_slots[event.category] += 1
            width = self._card_width(event, dense)
            widths[event.id] = width
            positions[event.id] = (x, lane_y - 29.0 + self._lane_offset(event))

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
