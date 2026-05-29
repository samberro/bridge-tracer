from __future__ import annotations

import httpx
import pytest
import time
from PySide6.QtCore import QCoreApplication, QEventLoop

from src.bridge_client.client import BridgeClient
from src.core.schemas import RecordingState
from src.ui.controller import BridgeTracerController, SSEStreamWorker


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class MockSSEClient(BridgeClient):
    def __init__(self, base_url: str, token: str | None = None, is_trace_available: bool = True) -> None:
        super().__init__(base_url, token, http_client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))))
        self._is_trace_available = is_trace_available

    def trace_available(self) -> bool:
        return self._is_trace_available


def test_sse_stream_worker_yields_events(qapp) -> None:
    sse_body = (
        "event: snapshot\n"
        "data: [{\"id\": \"evt_1\", \"type\": \"http.request\", \"category\": \"http\"}]\n\n"
        "event: trace\n"
        "data: {\"id\": \"evt_2\", \"type\": \"llm.request\", \"category\": \"llm\"}\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body.encode("utf-8"), headers={"content-type": "text/event-stream"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    worker = SSEStreamWorker("http://bridge.test", "t1", http_client=http)

    received_events = []
    worker.event_received.connect(received_events.append)

    worker.start()
    
    # Process events for 200ms
    start = time.time()
    while time.time() - start < 0.2:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 10)
        time.sleep(0.01)

    worker.stop()

    assert len(received_events) == 2
    assert received_events[0]["id"] == "evt_1"
    assert received_events[1]["id"] == "evt_2"


def test_sse_stream_worker_handles_errors(qapp) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"Internal server error")

    http = httpx.Client(transport=httpx.MockTransport(handler))
    worker = SSEStreamWorker("http://bridge.test", "t1", http_client=http)

    errors = []
    worker.error_occurred.connect(errors.append)

    worker.start()
    
    start = time.time()
    while not worker.isFinished() and time.time() - start < 2.0:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 10)
        time.sleep(0.01)

    for _ in range(5):
        QCoreApplication.processEvents(QEventLoop.AllEvents, 10)
        time.sleep(0.01)

    assert len(errors) == 1
    assert "upstream error" in errors[0].lower() or "500" in errors[0]


def test_controller_wires_sse_worker(qapp) -> None:
    sse_body = (
        "event: trace\n"
        "data: {\"id\": \"evt_live\", \"type\": \"http.request\", \"category\": \"http\"}\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body.encode("utf-8"), headers={"content-type": "text/event-stream"})

    http = httpx.Client(transport=httpx.MockTransport(handler))

    def client_factory(base_url: str, token: str | None = None) -> MockSSEClient:
        return MockSSEClient(base_url, token, is_trace_available=True)

    controller = BridgeTracerController(client_factory=client_factory)
    controller.connect("http://bridge.test", "t1")
    assert controller.trace_available() is True

    # Inject mock HTTP client for stream worker creation
    controller.set_worker_http_client(http)

    controller.start_recording()
    assert controller.status.recording_state == RecordingState.RECORDING
    assert controller.is_streaming is True

    # Process events for 200ms
    start = time.time()
    while time.time() - start < 0.2:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 10)
        time.sleep(0.01)

    controller.stop_recording()
    assert controller.status.recording_state == RecordingState.STOPPED
    assert controller.is_streaming is False

    events = controller.events
    assert len(events) == 1
    assert events[0].id == "evt_live"


def test_controller_falls_back_to_polling(qapp) -> None:
    def client_factory(base_url: str, token: str | None = None) -> MockSSEClient:
        return MockSSEClient(base_url, token, is_trace_available=False)

    controller = BridgeTracerController(client_factory=client_factory)
    controller.connect("http://bridge.test", "t1")
    assert controller.trace_available() is False

    controller.start_recording()
    assert controller.status.recording_state == RecordingState.RECORDING
    assert controller.is_streaming is False

    controller.stop_recording()
    assert controller.status.recording_state == RecordingState.STOPPED
