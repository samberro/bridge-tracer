"""End-to-end automation: drive the real window with real mouse clicks.

Uses QTest.mouseClick against actual widgets (not .click()) to prove the UI is
genuinely clickable — the regression the user reported. Performs a full user
flow: connect -> start -> select event -> stop -> save -> load.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from src.core.schemas import RecordingState
from src.ui.interactive_window import InteractiveTracerWindow
from src.ui.sample_data import build_sample_events


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _click(widget):
    QTest.mouseClick(widget, Qt.LeftButton)


def test_full_flow_with_real_mouse_clicks(qapp, tmp_path):
    w = InteractiveTracerWindow(events=build_sample_events())
    w.resize(1440, 900)
    w.show()

    # Type credentials and connect (real keyboard + mouse).
    w.url_edit.clear()
    QTest.keyClicks(w.url_edit, "http://127.0.0.1:8080")
    QTest.keyClicks(w.token_edit, "e2e-secret")
    _click(w.connect_btn)
    assert w.controller.status.connected is True
    assert "e2e-secret" not in w.status_label.text()

    # Start recording via a real click.
    _click(w.start_btn)
    assert w.controller.status.recording_state == RecordingState.RECORDING
    assert w.stop_btn.isEnabled() and not w.start_btn.isEnabled()

    # Click an event row (real click on the viewport at the row centre).
    item = w.event_list.topLevelItem(2)
    rect = w.event_list.visualItemRect(item)
    QTest.mouseClick(w.event_list.viewport(), Qt.LeftButton, pos=rect.center())
    assert w.inspector_text().strip() != ""
    assert "\"type\"" in w.inspector_text()

    # Stop recording. (This recording ingested no live events, so it is
    # legitimately empty — recording lifecycle is independent of the sample
    # data shown for browsing.)
    _click(w.stop_btn)
    assert w.controller.status.recording_state == RecordingState.STOPPED
    assert not w.stop_btn.isEnabled()
    w.close()


def test_save_and_load_roundtrip_with_real_clicks(qapp, tmp_path):
    # Persistence of the displayed events, via real Save/Load clicks.
    path = tmp_path / "e2e.json"
    saver = InteractiveTracerWindow(events=build_sample_events())
    saver.save_path_provider = lambda: path
    _click(saver.save_btn)
    assert path.exists()
    saver.close()

    loader = InteractiveTracerWindow(events=[])
    assert loader.event_count() == 0
    loader.open_path_provider = lambda: path
    _click(loader.load_btn)
    assert loader.event_count() == len(build_sample_events())
    assert loader.inspector_text().strip() != ""
    loader.close()
