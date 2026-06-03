"""§7 — pre-record filters scope capture; connection panel shows real state
without ever exposing the bearer token."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timezone

import pytest
from PySide6.QtWidgets import QApplication

from src.core.schemas import EventCategory, EventLevel, EventModel
from src.ui.controller import BridgeTracerController
from src.ui.interactive_window import InteractiveTracerWindow


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


class FakeClient:
    def __init__(self, base_url, token=None):
        pass

    def trace_available(self):
        return False

    def fetch_logs(self, limit=500):
        return []

    def list_events(self, *, since=None):
        return []

    def close(self):
        pass


def _ev(eid, cat, typ):
    return EventModel(id=eid, type=typ, category=cat, level=EventLevel.INFO,
                      summary=eid, timestamp=datetime(2026, 6, 2, 10, 0, 0, tzinfo=timezone.utc))


def _window():
    return InteractiveTracerWindow(events=[], controller=BridgeTracerController(client_factory=FakeClient))


def test_prerecord_filter_only_llm(qapp):
    w = _window()
    # Default records everything.
    assert w._build_prerecord_filter() is None

    w.prerecord_checks["Record everything"].setChecked(False)
    w.prerecord_checks["Only LLM traffic"].setChecked(True)
    fn = w._build_prerecord_filter()
    assert fn is not None
    assert fn(_ev("a", EventCategory.LLM, "llm.request")) is True
    assert fn(_ev("b", EventCategory.HTTP, "http.request")) is False
    w.close()
    w.deleteLater()


def test_prerecord_filter_drops_nonmatching_during_recording(qapp):
    w = _window()
    w.prerecord_checks["Record everything"].setChecked(False)
    w.prerecord_checks["Errors"].setChecked(True)
    w.url_edit.setText("http://bridge.local")
    w._on_connect()
    w._on_start()  # sets the prefilter on the recorder

    rec = w.controller._recorder
    rec.feed(_ev("err", EventCategory.ERROR, "parser.error"))
    rec.feed(_ev("ok", EventCategory.HTTP, "http.request"))
    ids = [e.id for e in w.controller.events]
    assert ids == ["err"]  # only the error was captured
    w._on_stop()
    w.close()
    w.deleteLater()


def test_connection_panel_never_shows_token(qapp):
    w = _window()
    w.url_edit.setText("http://bridge.local")
    w.token_edit.setText("supersecret-token")
    w._on_connect()
    w._refresh_connection_panel()
    assert w.conn_url_lbl.text() == "http://bridge.local"
    assert w.conn_token_lbl.text() == "present"
    assert "supersecret-token" not in w.conn_token_lbl.text()
    assert w.conn_auth_lbl.text() == "valid"
    w.close()
    w.deleteLater()
