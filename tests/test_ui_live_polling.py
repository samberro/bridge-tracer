"""The interactive window ingests live bridge events on Start (the recording
regression: 'bridge running but it's not recording')."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import httpx
import pytest
import time
from PySide6.QtCore import QCoreApplication, QEventLoop
from PySide6.QtWidgets import QApplication

from src.core.schemas import RecordingState
from src.ui.controller import BridgeTracerController
from src.ui.interactive_window import InteractiveTracerWindow


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _log(i):
    return {
        "id": f"log_{i}", "created_at": "2026-05-29T10:00:0%d+00:00" % (i % 10),
        "source": "llm", "direction": "output", "mode": "chat",
        "request_id": f"req_{i}", "session_id": "s", "run_id": "r",
        "status_code": 200, "ok": True, "payload": {"text": f"msg {i}"},
    }


def _controller_for(box):
    def handler(request: httpx.Request) -> httpx.Response:
        # 404 on /trace/events forces the log-polling fallback path (no SSE).
        if request.url.path == "/trace/events":
            return httpx.Response(404)
        return httpx.Response(200, json={"events": list(box)})

    def factory(*_a, **_k):
        from src.bridge_client.client import BridgeClient
        return BridgeClient("http://bridge.test", token="t",
                            http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    return BridgeTracerController(client_factory=factory)


def _pump_until(predicate, *, timeout_s: float = 1.5) -> None:
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline and not predicate():
        QCoreApplication.processEvents(QEventLoop.AllEvents, 20)
        time.sleep(0.01)


def test_start_ingests_live_bridge_events_into_timeline(qapp, monkeypatch):
    # Log-polling fallback (SSE unavailable). UI refresh is event-driven, so we
    # tick a poll and flush the debounced rebuild to observe the model.
    monkeypatch.setenv("AI_BRIDGE_RECORDING_FALLBACK", "logs")
    box = [_log(1), _log(2)]
    ctrl = _controller_for(box)
    ctrl.connect("http://bridge.test", "t")
    w = InteractiveTracerWindow(events=[], controller=ctrl)
    assert w.event_count() == 0

    w.start_btn.click()  # starts recording + fallback poll timer (no sync poll)
    assert ctrl.status.recording_state == RecordingState.RECORDING
    assert w.poll_once() == 2  # a timer tick ingests the two log events
    w._flush_pending_timeline_rebuild()
    assert w.event_count() == 2  # live events showed up in the list

    box.append(_log(3))      # a new bridge event arrives
    assert w.poll_once() == 1
    w._flush_pending_timeline_rebuild()
    assert w.event_count() == 3
    assert "3 events" in w.status_label.text()
    w.close()
    w.deleteLater()


def test_timer_poll_runs_async_and_skips_overlapping_ticks(qapp, monkeypatch):
    monkeypatch.setenv("AI_BRIDGE_RECORDING_FALLBACK", "logs")
    box = [_log(1)]
    calls = {"logs": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/trace/events":
            return httpx.Response(404)
        calls["logs"] += 1
        time.sleep(0.25)
        return httpx.Response(200, json={"events": list(box)})

    def factory(*_a, **_k):
        from src.bridge_client.client import BridgeClient
        return BridgeClient("http://bridge.test", token="t",
                            http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    ctrl = BridgeTracerController(client_factory=factory)
    ctrl.connect("http://bridge.test", "t")
    w = InteractiveTracerWindow(events=[], controller=ctrl)
    w.start_btn.click()

    start = time.perf_counter()
    assert w._poll_once_async() == 0
    elapsed = time.perf_counter() - start

    assert elapsed < 0.12
    assert w._async_runner.is_in_flight("poll")
    _pump_until(lambda: calls["logs"] == 1)
    assert w._poll_once_async() == 0
    assert calls["logs"] == 1

    _pump_until(lambda: not w._async_runner.is_in_flight("poll"))
    w._flush_pending_timeline_rebuild()

    assert calls["logs"] == 1
    assert w.event_count() == 1
    w.close()
    w.deleteLater()


def test_stop_halts_polling(qapp, monkeypatch):
    monkeypatch.setenv("AI_BRIDGE_RECORDING_FALLBACK", "logs")
    box = [_log(1)]
    ctrl = _controller_for(box)
    ctrl.connect("http://bridge.test", "t")
    w = InteractiveTracerWindow(events=[], controller=ctrl)
    w.start_btn.click()
    assert w.poll_once() == 1
    w._flush_pending_timeline_rebuild()
    assert w.event_count() == 1
    w.stop_btn.click()
    assert ctrl.status.recording_state == RecordingState.STOPPED
    assert not w._poll_timer.isActive()
    # further bridge events are not ingested once stopped
    box.append(_log(2))
    assert w.poll_once() == 0
    w.close()
    w.deleteLater()


def test_poll_error_surfaces_and_stops_timer(qapp, monkeypatch):
    monkeypatch.setenv("AI_BRIDGE_RECORDING_FALLBACK", "logs")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/trace/events":
            return httpx.Response(404)  # force fallback polling
        return httpx.Response(401, text="nope")  # /logs auth failure

    def factory(*_a, **_k):
        from src.bridge_client.client import BridgeClient
        return BridgeClient("http://bridge.test", token="bad",
                            http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    ctrl = BridgeTracerController(client_factory=factory)
    ctrl.connect("http://bridge.test", "bad")
    w = InteractiveTracerWindow(events=[], controller=ctrl)
    w.start_btn.click()
    w.poll_once()  # poll hits 401 on /logs
    assert "error" in w.status_label.text().lower()
    assert not w._poll_timer.isActive()
    w.close()
    w.deleteLater()
