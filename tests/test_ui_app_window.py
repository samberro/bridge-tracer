"""Smoke tests for the active window (``app_window.BridgeTracerWindow`` is an
alias of ``main_window.MainWindow``). The old hand-painted "mockup backdrop"
canvas was pruned, so these exercise the real window surface: visual states,
start/stop lifecycle, event selection → inspector, and screenshot capture.
A fake client keeps them off the network.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.core.schemas import RecordingState
from src.ui.app_window import BridgeTracerWindow
from src.ui.controller import BridgeTracerController
from src.ui.sample_data import build_sample_events


def _app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


class FakeBridgeClient:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url
        self.token = token
        self.closed = False
        self.events = [e.model_dump(mode="json") for e in build_sample_events()]

    def list_events(self, *, since: str | None = None):
        return self.events

    def fetch_logs(self, limit: int | None = 500):
        return []

    def trace_available(self) -> bool:
        # False keeps start_recording from spinning a real SSE worker thread.
        return False

    def safe_describe(self) -> str:
        return "fake-client"

    def close(self) -> None:
        self.closed = True


def _window(visual_state: str = "main_desktop_timeline") -> BridgeTracerWindow:
    ctrl = BridgeTracerController(client_factory=FakeBridgeClient)
    w = BridgeTracerWindow(events=build_sample_events(), visual_state=visual_state, controller=ctrl)
    w.resize(1440, 900)
    w.show()
    QApplication.processEvents()
    return w


def test_bridge_tracer_window_exposes_expected_visual_states() -> None:
    _app()
    w = _window()
    assert w.objectName() == "mainWindow"
    assert set(w.available_visual_states()) >= {
        "main_desktop_timeline",
        "filter_recording_sidebar",
        "event_detail_inspector",
        "timeline_filmstrip_focused",
    }
    w.close()
    w.deleteLater()


def test_bridge_tracer_window_start_stop_controls_update_state() -> None:
    _app()
    w = _window()
    w.url_edit.setText("http://bridge.local")
    w.token_edit.setText("secret-token")
    w._on_connect()
    w._on_start()
    assert w.controller.status.recording_state == RecordingState.RECORDING
    w._on_stop()
    assert w.controller.status.recording_state == RecordingState.STOPPED
    w.close()
    w.deleteLater()


def test_bridge_tracer_window_event_selection_updates_inspector() -> None:
    _app()
    w = _window("event_detail_inspector")
    w.select_event("evt_http_request")
    assert w.current_detail().title == "POST /api/send"
    w.close()
    w.deleteLater()


def test_bridge_tracer_window_can_capture_deterministic_screenshot(tmp_path: Path) -> None:
    _app()
    w = _window("timeline_filmstrip_focused")
    output = tmp_path / "timeline.png"
    w.grab().save(str(output))
    assert output.exists()
    assert output.stat().st_size > 0
    w.close()
    w.deleteLater()


def test_window_state_changes_after_start(tmp_path: Path) -> None:
    _app()
    w = _window()
    assert w.start_btn.isEnabled()
    w.url_edit.setText("http://bridge.local")
    w._on_connect()
    w._on_start()
    QApplication.processEvents()
    # Recording disables Start / enables Stop, and a screenshot still captures.
    assert not w.start_btn.isEnabled()
    assert w.stop_btn.isEnabled()
    output = tmp_path / "after.png"
    w.grab().save(str(output))
    assert output.exists() and output.stat().st_size > 0
    w.close()
    w.deleteLater()
