"""Real-network e2e: a live HTTP server mimics the bridge /logs endpoint; the
window records from it over a real socket (no MockTransport)."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from PySide6.QtWidgets import QApplication

from src.ui.controller import BridgeTracerController
from src.ui.interactive_window import InteractiveTracerWindow


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


_EVENTS = []


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_GET(self):
        if self.path.startswith("/logs"):
            body = json.dumps({"events": list(_EVENTS)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture
def bridge_server():
    _EVENTS.clear()
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield server, _EVENTS
    server.shutdown()


def _log(i):
    return {
        "id": f"log_{i}", "created_at": "2026-05-29T10:00:0%d+00:00" % (i % 10),
        "source": "llm", "direction": "output", "mode": "chat",
        "request_id": f"req_{i}", "session_id": "s", "run_id": "r",
        "status_code": 200, "ok": True, "payload": {"text": f"msg {i}"},
    }


def test_records_from_a_real_running_bridge(qapp, bridge_server, monkeypatch):
    # This bridge only serves /logs (404 on /trace/events), so it is the
    # log-polling fallback path. UI refresh is event-driven, so we tick a poll
    # and flush the debounced rebuild to observe the model.
    monkeypatch.setenv("AI_BRIDGE_RECORDING_FALLBACK", "logs")
    server, events = bridge_server
    port = server.server_address[1]
    events.extend([_log(1), _log(2)])

    ctrl = BridgeTracerController()
    ctrl.connect(f"http://127.0.0.1:{port}", "dev-token")
    w = InteractiveTracerWindow(events=[], controller=ctrl)

    w.start_btn.click()  # starts recording + fallback poll timer
    assert w.poll_once() == 2  # real HTTP poll of /logs over a socket
    w._flush_pending_timeline_rebuild()
    assert w.event_count() == 2

    events.append(_log(3))  # bridge emits another event
    assert w.poll_once() == 1
    w._flush_pending_timeline_rebuild()
    assert w.event_count() == 3
    assert w.controller.events[-1].type == "llm.response"
    w.close()
    w.deleteLater()
