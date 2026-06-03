"""§4 T4.3 — run/session selector scopes the timeline to a single run."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtWidgets import QApplication

from src.core.schemas import EventCategory, EventLevel, EventModel
from src.ui.interactive_window import InteractiveTracerWindow


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _ev(i, run):
    return EventModel(id=f"e{i}", type="http.request", category=EventCategory.HTTP,
                      level=EventLevel.INFO, summary=f"e{i}", run_id=run,
                      timestamp=datetime(2026, 6, 2, 10, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=i))


def test_run_selector_scopes_to_run(qapp):
    events = [_ev(0, "r1"), _ev(1, "r1"), _ev(2, "r1"), _ev(3, "r2"), _ev(4, "r2")]
    w = InteractiveTracerWindow(events=events)
    QApplication.processEvents()

    # All runs + r1 + r2.
    assert w.run_selector.count() == 3
    assert len(w._filtered_events()) == 5

    w.run_selector.setCurrentIndex(w.run_selector.findData("r1"))
    assert w._post_filter_run == "r1"
    assert len(w._filtered_events()) == 3

    w.run_selector.setCurrentIndex(0)  # All runs
    assert w._post_filter_run is None
    assert len(w._filtered_events()) == 5
    w.close()
    w.deleteLater()
