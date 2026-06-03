"""End-to-end automation: drive the real window with real mouse clicks.

Uses QTest.mouseClick against actual widgets (not .click()) to prove the UI is
genuinely clickable — the regression the user reported. Performs a full user
flow: connect -> start -> select event -> stop -> save -> load.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from src.core.schemas import RecordingState
from src.ui.controller import BridgeTracerController
from src.ui.interactive_window import InteractiveTracerWindow
from src.ui.sample_data import build_sample_events


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _click(widget):
    QTest.mouseClick(widget, Qt.LeftButton)


class FakeBridgeClient:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url
        self.token = token

    def trace_available(self) -> bool:
        return False

    def fetch_logs(self, limit=500):
        return []

    def list_events(self, *, since=None):
        return []

    def safe_describe(self) -> str:
        return f"base_url={self.base_url}; has_at={'yes' if self.token else 'no'}"

    def close(self) -> None:
        pass


def _pump_until(predicate, *, timeout_s: float = 1.5) -> None:
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline and not predicate():
        QCoreApplication.processEvents(QEventLoop.AllEvents, 20)
        time.sleep(0.01)


def test_full_flow_with_real_mouse_clicks(qapp, tmp_path):
    ctrl = BridgeTracerController(client_factory=FakeBridgeClient)
    w = InteractiveTracerWindow(events=build_sample_events(), controller=ctrl)
    w.resize(1440, 900)
    w.show()

    # Type credentials and connect (real keyboard + mouse).
    w.url_edit.clear()
    QTest.keyClicks(w.url_edit, "http://127.0.0.1:8080")
    QTest.keyClicks(w.token_edit, "e2e-secret")
    _click(w.connect_btn)
    _pump_until(lambda: w.controller.status.connected and not w._connect_in_flight)
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
    w.deleteLater()


def test_save_and_load_roundtrip_with_real_clicks(qapp, tmp_path):
    # Persistence of the displayed events, via real Save/Load clicks.
    path = tmp_path / "e2e.json"
    saver = InteractiveTracerWindow(events=build_sample_events())
    saver.save_path_provider = lambda: path
    _click(saver.save_btn)
    _pump_until(lambda: path.exists() and not saver._save_in_flight)
    assert path.exists()
    saver.close()
    saver.deleteLater()

    loader = InteractiveTracerWindow(events=[])
    assert loader.event_count() == 0
    loader.open_path_provider = lambda: path
    _click(loader.load_btn)
    _pump_until(lambda: loader.event_count() == len(build_sample_events()) and not loader._load_in_flight)
    assert loader.event_count() == len(build_sample_events())
    assert loader.inspector_text().strip() != ""
    loader.close()
    loader.deleteLater()
