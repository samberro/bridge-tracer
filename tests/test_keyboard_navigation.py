from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from src.core.schemas import RecordingState
from src.ui.interactive_window import InteractiveTracerWindow
from src.ui.sample_data import build_sample_events


def _window() -> InteractiveTracerWindow:
    w = InteractiveTracerWindow(events=build_sample_events())
    w.resize(1440, 900)
    w.show()
    QApplication.processEvents()
    return w


def test_slash_focuses_search_and_f_fits_timeline(qapp_session, monkeypatch) -> None:
    w = _window()
    called = {"fit": 0}
    monkeypatch.setattr(w.timeline_view, "fit_to_events", lambda: called.__setitem__("fit", called["fit"] + 1))

    QTest.keyClick(w, Qt.Key_Slash)
    assert QApplication.focusWidget() is w.post_search_edit

    w.setFocus()
    QTest.keyClick(w, Qt.Key_F)
    assert called["fit"] == 1
    w.close()
    w.deleteLater()


def test_up_down_shortcuts_move_visible_selection(qapp_session) -> None:
    w = _window()
    first = w.model.events[0].id
    second = w.model.events[1].id
    w.select_event(first)

    QTest.keyClick(w, Qt.Key_Down)
    assert w.model.selected_event_id == second

    QTest.keyClick(w, Qt.Key_Up)
    assert w.model.selected_event_id == first
    w.close()
    w.deleteLater()


def test_escape_clears_selection(qapp_session) -> None:
    w = _window()
    w.select_event(w.model.events[0].id)

    QTest.keyClick(w, Qt.Key_Escape)

    assert w.model.selected_event_id is None
    assert w.event_list.currentItem() is None
    assert w.timeline_view.selected_event_id is None
    w.close()
    w.deleteLater()


def test_space_toggles_start_and_stop(qapp_session) -> None:
    w = _window()

    QTest.keyClick(w, Qt.Key_Space)
    assert w.controller.status.recording_state == RecordingState.RECORDING

    QTest.keyClick(w, Qt.Key_Space)
    assert w.controller.status.recording_state == RecordingState.STOPPED
    w.close()
    w.deleteLater()
