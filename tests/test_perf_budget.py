from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import QCoreApplication

from src.core.schemas import EventCategory, EventLevel, EventModel
from src.ui.interactive_window import InteractiveTracerWindow


_CATEGORIES = (
    EventCategory.HTTP,
    EventCategory.LLM,
    EventCategory.TOOL,
    EventCategory.FILE,
    EventCategory.ERROR,
    EventCategory.PERFORMANCE,
)


def _volume_events(count: int = 360) -> list[EventModel]:
    base = datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)
    events: list[EventModel] = []
    for index in range(count):
        category = _CATEGORIES[index % len(_CATEGORIES)]
        events.append(
            EventModel(
                id=f"evt_perf_{index:04d}",
                type=f"{category.value}.event",
                category=category,
                level=EventLevel.ERROR if index % 29 == 0 else EventLevel.INFO,
                summary=(
                    f"perf search target {index}"
                    if index % 17 == 0
                    else f"perf event {index}"
                ),
                timestamp=base + timedelta(milliseconds=index * 50),
                run_id=f"run_{index % 4}",
                request_id=f"req_{index % 20}",
                details={"index": index, "payload": f"value-{index}"},
                duration_ms=float(index % 250),
            )
        )
    return events


def test_360_event_timeline_rebuild_and_filter_stay_under_budget(qapp_session) -> None:
    events = _volume_events()
    window = InteractiveTracerWindow(events=events)
    window.resize(1440, 900)
    window.show()
    QCoreApplication.processEvents()

    started = time.perf_counter()
    window._rebuild_timeline()
    QCoreApplication.processEvents()
    rebuild_ms = (time.perf_counter() - started) * 1000

    # A local probe is ~55 ms; keep a generous ceiling for slower CI machines
    # while still catching regressions back to sluggish full rebuilds.
    assert rebuild_ms < 180, f"360-event rebuild too slow: {rebuild_ms:.1f} ms"
    assert len(window.timeline_view.items_map) + len(window.timeline_view.collection_items) > 0

    started = time.perf_counter()
    window.post_search_edit.setText("search target")
    window._on_post_filter_changed()
    QCoreApplication.processEvents()
    filter_ms = (time.perf_counter() - started) * 1000

    assert filter_ms < 80, f"360-event filter too slow: {filter_ms:.1f} ms"
    assert 0 < len(window._filtered_events()) < len(events)
    assert window.event_list.topLevelItemCount() == len(window._filtered_events())

    window.close()
    window.deleteLater()
