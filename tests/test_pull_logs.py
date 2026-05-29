"""Tests for live ingestion: BridgeClient.fetch_logs + controller.pull_logs."""
from __future__ import annotations

import httpx

from src.bridge_client.client import BridgeClient
from src.ui.controller import BridgeTracerController


def _log(i, direction="output"):
    return {
        "id": f"log_{i}", "created_at": "2026-05-29T10:00:0%d+00:00" % (i % 10),
        "source": "llm", "direction": direction, "mode": "chat",
        "request_id": f"req_{i}", "session_id": "s", "run_id": "r",
        "status_code": 200, "ok": True, "payload": {"text": f"msg {i}"},
    }


def _client(events_box):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/trace/events":
            return httpx.Response(404)
        assert request.url.path == "/logs"
        return httpx.Response(200, json={"events": list(events_box)})
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return BridgeClient("http://bridge.test", token="t", http_client=http)


def test_fetch_logs_unwraps_events_envelope():
    c = _client([_log(1), _log(2)])
    out = c.fetch_logs(limit=100)
    assert [e["id"] for e in out] == ["log_1", "log_2"]


def test_pull_logs_records_only_while_recording():
    box = [_log(1)]
    ctrl = BridgeTracerController(client_factory=lambda *a, **k: _client(box))
    ctrl.connect("http://bridge.test", "t")
    # not recording yet -> no-op
    assert ctrl.pull_logs() == 0
    ctrl.start_recording()
    assert ctrl.pull_logs() == 1
    assert len(ctrl.events) == 1
    assert ctrl.events[0].type == "llm.response"


def test_pull_logs_dedupes_repeated_polls():
    box = [_log(1), _log(2)]
    ctrl = BridgeTracerController(client_factory=lambda *a, **k: _client(box))
    ctrl.connect("http://bridge.test", "t")
    ctrl.start_recording()
    assert ctrl.pull_logs() == 2
    # /logs returns the same window again; nothing new should be added
    assert ctrl.pull_logs() == 0
    # a new event appears -> only that one is added
    box.append(_log(3))
    assert ctrl.pull_logs() == 1
    assert len(ctrl.events) == 3


def test_pull_logs_resets_dedup_on_new_recording():
    box = [_log(1)]
    ctrl = BridgeTracerController(client_factory=lambda *a, **k: _client(box))
    ctrl.connect("http://bridge.test", "t")
    ctrl.start_recording()
    assert ctrl.pull_logs() == 1
    ctrl.stop_recording()
    # A fresh recording should re-capture (seen-set cleared on start).
    ctrl.start_recording()
    assert ctrl.pull_logs() == 1


def test_pull_logs_without_client_is_noop():
    ctrl = BridgeTracerController()
    ctrl.start_recording()
    assert ctrl.pull_logs() == 0
