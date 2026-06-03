"""§4 T4.1/T4.2 — cached text search (correct + memoized) and O(1) list
selection sync."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from src.core.schemas import EventCategory
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


def test_filter_presets_persist_apply_and_delete(qapp, tmp_path):
    ini = str(tmp_path / "filter-presets.ini")
    w1 = InteractiveTracerWindow(events=build_sample_events())
    w1._settings = QSettings(ini, QSettings.IniFormat)

    w1.post_search_edit.setText("llm")
    w1.post_errors_only_chk.setChecked(True)
    for category, chk in w1.post_category_checks.items():
        chk.setChecked(category in {EventCategory.LLM, EventCategory.ERROR})
    idx = w1.run_selector.findData("run_8f31b2")
    assert idx >= 0
    w1.run_selector.setCurrentIndex(idx)
    w1.preset_name_edit.setText("LLM errors")

    w1._save_filter_preset()
    assert "LLM errors" in w1._filter_preset_names()
    w1.close()
    w1.deleteLater()

    w2 = InteractiveTracerWindow(events=build_sample_events())
    w2._settings = QSettings(ini, QSettings.IniFormat)
    w2._refresh_filter_presets()

    assert "LLM errors" in w2._filter_preset_names()

    w2._clear_post_filters()
    assert w2.post_search_edit.text() == ""
    assert w2._post_filter_run is None

    w2.preset_selector.setCurrentIndex(w2.preset_selector.findText("LLM errors"))
    w2._apply_filter_preset()

    assert w2.post_search_edit.text() == "llm"
    assert w2.post_errors_only_chk.isChecked()
    assert w2._post_filter_run == "run_8f31b2"
    selected = {category for category, chk in w2.post_category_checks.items() if chk.isChecked()}
    assert selected == {EventCategory.LLM, EventCategory.ERROR}

    w2._delete_filter_preset()
    assert "LLM errors" not in w2._filter_preset_names()
    w2.close()
    w2.deleteLater()
