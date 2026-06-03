"""§1 T1.3 / §5 T5.9 — the toolbar status pill reflects recording/stream state
and never leaks the bearer token."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from src.ui.controller import BridgeTracerController
from src.ui.interactive_window import InteractiveTracerWindow
from src.ui.sample_data import build_sample_events


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


class FakeBridgeClient:
    def __init__(self, base_url, token=None):
        self.base_url = base_url
        self.token = token

    def trace_available(self):
        return False  # avoid spinning a real SSE worker

    def fetch_logs(self, limit=500):
        return []

    def list_events(self, *, since=None):
        return []

    def close(self):
        pass


def test_status_pill_reflects_lifecycle_and_hides_token(qapp):
    ctrl = BridgeTracerController(client_factory=FakeBridgeClient)
    w = InteractiveTracerWindow(events=build_sample_events(), controller=ctrl)
    w.url_edit.setText("http://bridge.local")
    w.token_edit.setText("secret-xyz")

    w._on_connect()
    assert "ready" in w.status_label.text().lower()

    w._on_start()
    txt = w.status_label.text()
    assert "recording" in txt.lower()
    assert "22c55e" in txt.lower()           # green live dot
    assert "secret-xyz" not in txt           # never leak the token
    assert "events" in txt.lower()

    w._on_stop()
    assert "stopped" in w.status_label.text().lower()
    w.close()
    w.deleteLater()
