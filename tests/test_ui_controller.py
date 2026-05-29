from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.schemas import RecordingState
from src.ui.controller import BridgeTracerController
from src.ui.sample_data import build_sample_events


class FakeBridgeClient:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url
        self.token = token
        self.closed = False
        self.events = [event.model_dump(mode="json") for event in build_sample_events()]

    def list_events(self, *, since: str | None = None) -> list[dict[str, Any]]:
        assert since is None or isinstance(since, str)
        return self.events

    def trace_available(self) -> bool:
        return True

    def close(self) -> None:
        self.closed = True


def test_controller_connects_without_exposing_bearer_token() -> None:
    controller = BridgeTracerController(client_factory=FakeBridgeClient)

    status = controller.connect("http://bridge.local", "secret-token")

    assert status.connected is True
    assert status.label == "token/auth: valid - ws connected"
    assert "secret-token" not in status.safe_description


def test_controller_start_pull_stop_lifecycle() -> None:
    controller = BridgeTracerController(client_factory=FakeBridgeClient)
    controller.connect("http://bridge.local", "secret-token")

    controller.start_recording()
    accepted = controller.pull_once()
    metadata = controller.stop_recording()

    assert accepted == len(build_sample_events())
    assert metadata.state == RecordingState.STOPPED
    assert metadata.event_count == len(build_sample_events())
    assert controller.status.recording_state == RecordingState.STOPPED


def test_controller_save_and_load_recording_round_trip(tmp_path: Path) -> None:
    controller = BridgeTracerController(client_factory=FakeBridgeClient)
    controller.connect("http://bridge.local", "secret-token")
    controller.start_recording()
    controller.pull_once()
    controller.stop_recording()

    path = tmp_path / "recording.json"
    controller.save_recording(path)

    loaded = BridgeTracerController(client_factory=FakeBridgeClient)
    loaded.load_recording(path)

    assert len(loaded.events) == len(controller.events)
    assert loaded.events[0].id == controller.events[0].id
