from __future__ import annotations

from src.core.schemas import RecordingState
from src.ui import controller as controller_module
from src.ui.controller import BridgeTracerController
from src.ui.interactive_window import InteractiveTracerWindow


class FakeClient:
    def __init__(self, *, trace_available: bool = True) -> None:
        self._base_url = "http://bridge.invalid"
        self._token = "token"
        self._trace_available = trace_available
        self.fetch_logs_calls = 0
        self.list_events_calls = 0
        self.closed = False

    def trace_available(self) -> bool:
        return self._trace_available

    def fetch_logs(self, limit: int | None = 500):
        self.fetch_logs_calls += 1
        return []

    def list_events(self, since: str | None = None):
        self.list_events_calls += 1
        return []

    def safe_describe(self) -> str:
        return "fake-client"

    def close(self) -> None:
        self.closed = True


class FakeSignal:
    def connect(self, *args, **kwargs) -> None:
        pass

    def disconnect(self, *args, **kwargs) -> None:
        pass


class FakeSSEWorker:
    created: list["FakeSSEWorker"] = []

    def __init__(self, base_url: str, at: str | None = None, *, http_client=None,
                 read_timeout: float = 15.0) -> None:
        self.base_url = base_url
        self.at = at
        self.http_client = http_client
        self.read_timeout = read_timeout
        self.started = False
        self.stopped = False
        self.event_received = FakeSignal()
        self.error_occurred = FakeSignal()
        self.reconnecting = FakeSignal()
        FakeSSEWorker.created.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def isRunning(self) -> bool:
        return self.started and not self.stopped


class FakeTimer:
    def __init__(self) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


class DummyWindow:
    def __init__(self) -> None:
        self.controller = BridgeTracerController()
        self.controller._client = FakeClient(trace_available=True)
        self.controller.status = self.controller.status.__class__(
            connected=True,
            recording_state=RecordingState.IDLE,
        )
        self._poll_timer = FakeTimer()
        self.poll_once_called = False
        self.refresh_controls_called = 0

    def _on_connect(self) -> None:
        raise AssertionError("test starts connected")

    def _refresh_controls(self) -> None:
        self.refresh_controls_called += 1

    def _poll_once(self) -> int:
        self.poll_once_called = True
        raise AssertionError("SSE recording must not poll logs")


def test_start_recording_uses_sse_without_polling_logs(monkeypatch) -> None:
    fake_client = FakeClient(trace_available=True)
    controller = BridgeTracerController()
    controller._client = fake_client
    FakeSSEWorker.created.clear()
    monkeypatch.setattr(controller_module, "SSEStreamWorker", FakeSSEWorker)

    controller.start_recording()

    assert controller.status.recording_state == RecordingState.RECORDING
    assert fake_client.fetch_logs_calls == 0
    assert len(FakeSSEWorker.created) == 1
    assert FakeSSEWorker.created[0].started is True


def test_no_log_polling_when_sse_unavailable_without_explicit_fallback(monkeypatch) -> None:
    fake_client = FakeClient(trace_available=False)
    controller = BridgeTracerController()
    controller._client = fake_client
    monkeypatch.delenv("AI_BRIDGE_RECORDING_FALLBACK", raising=False)

    controller.start_recording()
    new_count = controller.pull_logs()

    assert controller.status.recording_state == RecordingState.RECORDING
    assert controller.is_log_fallback is False
    assert new_count == 0
    assert fake_client.fetch_logs_calls == 0


def test_explicit_log_fallback_allows_polling(monkeypatch) -> None:
    fake_client = FakeClient(trace_available=False)
    controller = BridgeTracerController()
    controller._client = fake_client
    monkeypatch.setenv("AI_BRIDGE_RECORDING_FALLBACK", "logs")

    controller.start_recording()
    new_count = controller.pull_logs()

    assert controller.status.recording_state == RecordingState.RECORDING
    assert controller.is_log_fallback is True
    assert new_count == 0
    assert fake_client.fetch_logs_calls == 1


def test_window_start_does_not_start_poll_timer_without_fallback(monkeypatch) -> None:
    dummy = DummyWindow()
    FakeSSEWorker.created.clear()
    monkeypatch.setattr(controller_module, "SSEStreamWorker", FakeSSEWorker)
    monkeypatch.delenv("AI_BRIDGE_RECORDING_FALLBACK", raising=False)

    InteractiveTracerWindow._on_start(dummy)

    assert dummy.controller.status.recording_state == RecordingState.RECORDING
    assert dummy._poll_timer.started is False
    assert dummy.poll_once_called is False


def test_window_start_starts_poll_timer_only_in_log_fallback(monkeypatch) -> None:
    dummy = DummyWindow()
    dummy.controller._client = FakeClient(trace_available=False)
    monkeypatch.setenv("AI_BRIDGE_RECORDING_FALLBACK", "logs")

    InteractiveTracerWindow._on_start(dummy)

    assert dummy.controller.status.recording_state == RecordingState.RECORDING
    assert dummy._poll_timer.started is True
