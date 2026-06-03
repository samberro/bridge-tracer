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


def test_fit_layout_has_no_overlap_and_bounded_gaps() -> None:
    """At real volume the fit layout must not stack cards on top of each other,
    and a long idle gap must be compressed, not rendered as a sparse void."""
    view = TimelineView()
    events = [_event(f"b{i}", 0) for i in range(100)]            # same-instant burst
    events += [_event(f"g{i}", 3600 + i) for i in range(100)]   # after a 1h idle
    lanes = view._active_lanes(events)
    view._lane_y = {cat: 88.0 + i * 86.0 for i, cat in enumerate(lanes)}
    pos, widths = view._layout_events(events, lanes, "main_desktop_timeline")

    ordered = sorted(((pos[e.id][0], widths[e.id]) for e in events), key=lambda t: t[0])
    # No two cards in the (single) HTTP lane overlap.
    for (x1, w1), (x2, _w2) in zip(ordered, ordered[1:]):
        assert x2 >= x1 + w1 - 0.001, "fit layout overlaps cards"
    # The 1h idle gap is compressed to a bounded width, not ~hours of pixels.
    max_gap = max(x2 - (x1 + w1) for (x1, w1), (x2, _w2) in zip(ordered, ordered[1:]))
    assert max_gap < 400, f"idle gap not compressed: {max_gap}"


def test_dense_burst_collapses_into_one_collection_card() -> None:
    view = TimelineView()
    events = [_event(f"b{i}", i) for i in range(12)]  # 12 consecutive HTTP events
    view.populate_events(events, "main_desktop_timeline")
    assert len(view.collection_items) == 1
    assert len(view.items_map) == 0  # individuals are hidden while collapsed
    col = next(iter(view.collection_items.values()))
    assert col.count == 12


def test_expanding_collection_reveals_individuals_then_collapses() -> None:
    view = TimelineView()
    events = [_event(f"b{i}", i) for i in range(12)]
    view.populate_events(events, "main_desktop_timeline")
    gid = next(iter(view.collection_items))

    view._on_collection_clicked(gid)  # fan out
    assert len(view.items_map) == 12
    assert len(view.collection_items) == 0

    view.collapse_all_groups()  # re-collapse
    assert len(view.collection_items) == 1
    assert len(view.items_map) == 0


def test_short_runs_are_not_collapsed() -> None:
    view = TimelineView()
    events = [_event(f"s{i}", i) for i in range(3)]  # below COLLAPSE_MIN
    view.populate_events(events, "main_desktop_timeline")
    assert len(view.collection_items) == 0
    assert len(view.items_map) == 3


def test_selecting_event_does_not_force_scroll_on_rebuild(monkeypatch) -> None:
    view = TimelineView()
    calls = []
    monkeypatch.setattr(view, "ensureVisible", lambda *args, **kwargs: calls.append((args, kwargs)))

    view.populate_events([_event("a", 0), _event("b", 1)], "main_desktop_timeline")
    view.set_selected_event("b")

    assert calls == []
