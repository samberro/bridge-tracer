from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.bridge_client.client import BridgeClient
from src.core.recorder import Recorder
from src.core.schemas import EventModel, RecordingMetadata, RecordingState
from src.core.storage import RecordingStorage


@dataclass(frozen=True)
class ControllerStatus:
    connected: bool = False
    label: str = "token/auth: unknown - disconnected"
    safe_description: str = ""
    recording_state: RecordingState = RecordingState.IDLE


class BridgeTracerController:
    def __init__(self, *, client_factory: Callable[..., BridgeClient] = BridgeClient) -> None:
        self._client_factory = client_factory
        self._client = None
        self._recorder = Recorder(on_state_change=self._on_recording_state_change)
        self._events: list[EventModel] = []
        self.status = ControllerStatus()

    @property
    def events(self) -> list[EventModel]:
        if self._recorder.events:
            return self._recorder.sorted_events()
        return list(self._events)

    def set_events(self, events: list[EventModel]) -> None:
        """Seed the controller's standing events (used when the UI is opened
        with sample/loaded data before any live recording)."""
        self._events = list(events)

    def connect(self, base_url: str, token: str | None = None) -> ControllerStatus:
        self.disconnect()
        self._client = self._client_factory(base_url, token)
        safe = ""
        if hasattr(self._client, "safe_describe"):
            safe = str(self._client.safe_describe())
        else:
            safe = f"base_url={base_url}; has_token={'yes' if token else 'no'}"
        if token:
            safe = safe.replace(token, "[REDACTED]")
        self.status = ControllerStatus(
            connected=True,
            label="token/auth: valid - ws connected",
            safe_description=safe,
            recording_state=self._recorder.state,
        )
        return self.status

    def disconnect(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()
        self._client = None
        if self.status.connected:
            self.status = ControllerStatus(recording_state=self._recorder.state)

    def start_recording(self) -> None:
        if self._recorder.state == RecordingState.STOPPED:
            self._recorder = Recorder(on_state_change=self._on_recording_state_change)
        self._recorder.start()
        self._on_recording_state_change(RecordingState.IDLE, self._recorder.state)

    def pull_once(self, *, since: str | None = None) -> int:
        if self._client is None:
            return 0
        return self._recorder.feed_many(self._client.list_events(since=since))

    def stop_recording(self) -> RecordingMetadata:
        metadata = self._recorder.stop()
        self._events = self._recorder.sorted_events()
        self._on_recording_state_change(RecordingState.STOPPING, self._recorder.state)
        return metadata

    def save_recording(self, path: Path) -> Path:
        return RecordingStorage.save_json(path, self._recorder.metadata, self.events)

    def load_recording(self, path: Path) -> list[str]:
        metadata, events, errors = RecordingStorage.load_json(path)
        self._events = events
        self._recorder = Recorder(on_state_change=self._on_recording_state_change)
        self.status = ControllerStatus(
            connected=self.status.connected,
            label=self.status.label,
            safe_description=self.status.safe_description,
            recording_state=metadata.state,
        )
        return errors

    def _on_recording_state_change(self, _previous: RecordingState, target: RecordingState) -> None:
        self.status = ControllerStatus(
            connected=self.status.connected,
            label=self.status.label,
            safe_description=self.status.safe_description,
            recording_state=target,
        )

