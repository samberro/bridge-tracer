"""Regression guard for the core recording bug (diagnostic-baseline.md):

With polling disabled (SSE mode), live events must reach the UI *model*, not
just the recorder. Previously the window only synced recorder→model via the
poll timer, so SSE recording showed nothing. This drives a fake SSE stream and
asserts the event-driven refresh updates event_count() with zero /logs calls.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import httpx
import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop
from PySide6.QtWidgets import QApplication

from src.bridge_client.client import BridgeClient
from src.core.schemas import RecordingState
from src.ui.controller import BridgeTracerController
from src.ui.interactive_window import InteractiveTracerWindow


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


class _TraceClient(BridgeClient):
    """Client whose /trace/events is available (SSE path), and that counts any
    /logs poll so we can assert we never poll in SSE mode."""

    def __init__(self, base_url, token=None):
        super().__init__(base_url, token,
                         http_client=httpx.Client(transport=httpx.MockTransport(
                             lambda r: httpx.Response(200))))
        self.fetch_logs_calls = 0

    def trace_available(self) -> bool:
        return True

    def fetch_logs(self, *, limit=None):
        self.fetch_logs_calls += 1
        return []


def _pump(seconds: float) -> None:
    start = time.time()
    while time.time() - start < seconds:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 10)
        time.sleep(0.01)


def test_live_sse_events_reach_the_ui_model_without_polling(qapp):
    sse_body = (
        "event: snapshot\n"
        "data: [{\"id\": \"evt_a\", \"type\": \"http.request\", \"category\": \"http\"}]\n\n"
        "event: trace\n"
        "data: {\"id\": \"evt_b\", \"type\": \"llm.request\", \"category\": \"llm\"}\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body.encode("utf-8"),
                              headers={"content-type": "text/event-stream"})

    sse_http = httpx.Client(transport=httpx.MockTransport(handler))

    client = _TraceClient("http://bridge.test", "t")
    ctrl = BridgeTracerController(client_factory=lambda *a, **k: client)
    ctrl.connect("http://bridge.test", "t")
    ctrl.set_worker_http_client(sse_http)

    w = InteractiveTracerWindow(events=[], controller=ctrl)
    assert w.event_count() == 0

    w._on_start()  # SSE-first: starts the stream worker, no poll timer
    assert ctrl.status.recording_state == RecordingState.RECORDING
    assert ctrl.is_streaming is True
    assert ctrl.is_log_fallback is False
    assert not w._poll_timer.isActive()

    _pump(0.3)  # deliver queued SSE signals to the GUI thread
    w._flush_pending_timeline_rebuild()

    # The live events reached the UI MODEL (the regression that was broken).
    assert w.event_count() == 2, "live SSE events did not reach the UI model"
    assert client.fetch_logs_calls == 0, "must not poll /logs in SSE mode"

    w._on_stop()
    _pump(0.1)
    assert ctrl.status.recording_state == RecordingState.STOPPED
    assert ctrl.is_streaming is False
    w.close()
    w.deleteLater()
