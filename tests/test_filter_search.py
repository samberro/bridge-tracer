"""§4 T4.1/T4.2 — cached text search (correct + memoized) and O(1) list
selection sync."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from src.ui.interactive_window import InteractiveTracerWindow
from src.ui.sample_data import build_sample_events


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_text_filter_matches_and_memoizes(qapp):
    w = InteractiveTracerWindow(events=build_sample_events())
    total = w.event_count()

    w.post_search_edit.setText("llm")
    w._on_post_filter_changed()  # apply immediately (bypasses the debounce timer)
    shown = len(w._filtered_events())
    assert 0 < shown <= total
    assert len(w._haystack_cache) > 0  # haystacks were cached

    w._clear_post_filters()
    assert len(w._filtered_events()) == total
    w.close()
    w.deleteLater()


def test_selection_sync_is_constant_time(qapp):
    w = InteractiveTracerWindow(events=build_sample_events())
    # The id->item map covers every visible row.
    assert len(w._list_item_by_id) == w.event_count()

    target = w.model.events[-1].id
    w.select_event(target)
    current = w.event_list.currentItem()
    assert current is not None
    from src.ui.main_window import _ID_ROLE
    assert current.data(0, _ID_ROLE) == target
    w.close()
    w.deleteLater()
