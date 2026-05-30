from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.core.schemas import EventCategory, EventLevel, EventModel
from src.ui.timeline_view import TimelineView


def _event(event_id: str, seconds: int, category: EventCategory = EventCategory.HTTP) -> EventModel:
    return EventModel(
        id=event_id,
        type="http.response",
        category=category,
        level=EventLevel.INFO,
        summary=f"event {event_id}",
        timestamp=datetime(2026, 5, 30, 7, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds),
    )


def test_existing_event_positions_do_not_shift_when_new_events_arrive() -> None:
    view = TimelineView()
    events = [_event("a", 0), _event("b", 1), _event("c", 2)]
    lanes = view._active_lanes(events)
    view._lane_y = {cat: 88.0 + i * 86.0 for i, cat in enumerate(lanes)}
    before, _ = view._layout_events(events, lanes, "main_desktop_timeline")

    appended = events + [_event("d", 20), _event("e", 40)]
    lanes_after = view._active_lanes(appended)
    view._lane_y = {cat: 88.0 + i * 86.0 for i, cat in enumerate(lanes_after)}
    after, _ = view._layout_events(appended, lanes_after, "main_desktop_timeline")

    assert after["a"] == before["a"]
    assert after["b"] == before["b"]
    assert after["c"] == before["c"]


def test_selecting_event_does_not_force_scroll_on_rebuild(monkeypatch) -> None:
    view = TimelineView()
    calls = []
    monkeypatch.setattr(view, "ensureVisible", lambda *args, **kwargs: calls.append((args, kwargs)))

    view.populate_events([_event("a", 0), _event("b", 1)], "main_desktop_timeline")
    view.set_selected_event("b")

    assert calls == []
