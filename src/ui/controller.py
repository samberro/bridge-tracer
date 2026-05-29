from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread, Signal

from src.bridge_client.client import BridgeClient
from src.bridge_client.stream import SSEEventSource
from src.core.bridge_log import map_log_event
from src.core.recorder import Recorder
from src.core.schemas import EventModel, RecordingMetadata, RecordingState
from src.core.storage import RecordingStorage


import threading

class SSEStreamWorker(QThread):
    event_received = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, base_url: str, token: str | None = None, *, http_client=None) -> None:
        super().__init__()
        self.base_url = base_url
        self.token = token
        self.http_client = http_client
        self._lock = threading.Lock()
        self._running = True
        self._source = None

    def run(self) -> None:
        with self._lock:
            if not self._running:
                return
            try:
                self._source = SSEEventSource(self.base_url, self.token, http_client=self.http_client)
            except Exception as exc:
                if self._running:
                    self.error_occurred.emit(str(exc))
                return

        try:
            with self._source as source:
                for msg in source:
                    with self._lock:
                        if not self._running:
                            break
                    if msg.event in ("trace", "snapshot") and msg.data:
                        try:
                            data = json.loads(msg.data)
                            with self._lock:
                                if not self._running:
                                    break
                                if isinstance(data, list):
                                    for item in data:
                                        self.event_received.emit(item)
                                elif isinstance(data, dict):
                                    self.event_received.emit(data)
                        except Exception:
                            pass
        except Exception as exc:
            with self._lock:
                if self._running:
                    self.error_occurred.emit(str(exc))

    def stop(self) -> None:
        with self._lock:
            self._running = False
            if self._source:
                try:
                    self._source.close()
                except Exception:
                    pass
        self.quit()
        self.wait()


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
        self._seen_ids: set[str] = set()
        self.status = ControllerStatus()
        self._worker: SSEStreamWorker | None = None
        self._worker_http_client = None

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

        trace_ok = self.trace_available()
        label = "token/auth: valid - ws connected" if trace_ok else "token/auth: valid - connected"
        self.status = ControllerStatus(
            connected=True,
            label=label,
            safe_description=safe,
            recording_state=self._recorder.state,
        )
        return self.status

    def disconnect(self) -> None:
        self._stop_stream_worker()
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()
        self._client = None
        if self.status.connected:
            self.status = ControllerStatus(recording_state=self._recorder.state)

    def trace_available(self) -> bool:
        if self._client is None:
            return False
        if hasattr(self._client, "trace_available"):
            return self._client.trace_available()
        return False

    def set_worker_http_client(self, client) -> None:
        self._worker_http_client = client

    @property
    def is_streaming(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _on_stream_event(self, raw_evt: dict) -> None:
        if self._recorder.state != RecordingState.RECORDING:
            return
        event = self._recorder.feed(raw_evt)
        if event is not None:
            self._seen_ids.add(event.id)

    def _stop_stream_worker(self) -> None:
        if self._worker is not None:
            try:
                self._worker.stop()
            except Exception:
                pass
            self._worker = None

    def start_recording(self) -> None:
        if self._recorder.state == RecordingState.STOPPED:
            self._recorder = Recorder(
                on_state_change=self._on_recording_state_change,
                on_stop_subscriptions=self._stop_stream_worker
            )
        else:
            self._recorder._on_stop_subscriptions = self._stop_stream_worker
            
        self._seen_ids = set()
        self._recorder.start()

        if self.trace_available():
            base_url = self._client._base_url if hasattr(self._client, "_base_url") else ""
            token = self._client._token if hasattr(self._client, "_token") else None
            self._worker = SSEStreamWorker(
                base_url=base_url,
                token=token,
                http_client=self._worker_http_client
            )
            self._worker.event_received.connect(self._on_stream_event)
            self._worker.start()

        self._on_recording_state_change(RecordingState.IDLE, self._recorder.state)

    def pull_once(self, *, since: str | None = None) -> int:
        if self._client is None:
            return 0
        return self._recorder.feed_many(self._client.list_events(since=since))

    def pull_logs(self, *, limit: int | None = 500) -> int:
        """Poll the bridge's /logs endpoint and feed NEW events into the
        recorder. Returns the count of newly recorded events.

        De-dupes by event id (each poll returns the last N logs), and only
        records while RECORDING so polling outside a session is a no-op.
        """
        if self._client is None or self._recorder.state != RecordingState.RECORDING:
            return 0
        raw_events = self._client.fetch_logs(limit=limit)
        new_count = 0
        for raw in raw_events:
            event = map_log_event(raw) if isinstance(raw, dict) else None
            if event is None or event.id in self._seen_ids:
                continue
            if self._recorder.feed(event) is not None:
                self._seen_ids.add(event.id)
                new_count += 1
        return new_count

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

