from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal, Qt

from src.bridge_client.client import BridgeClient
from src.bridge_client.stream import SSEEventSource
from src.core.bridge_log import map_log_event
from src.core.recorder import Recorder
from src.core.schemas import EventModel, RecordingMetadata, RecordingState
from src.core.storage import RecordingStorage


def _env_auth_token() -> str | None:
    token = os.environ.get("AI_BRIDGE_ADMIN_TOKEN")
    if token is None:
        return None
    token = token.strip()
    if not token:
        return None
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token or None


def _log_fallback_enabled() -> bool:
    return os.environ.get("AI_BRIDGE_RECORDING_FALLBACK", "").strip().casefold() in {
        "log",
        "logs",
        "poll",
        "poll_logs",
    }


class SSEStreamWorker(QObject):
    """SSE stream worker backed by threading.Thread instead of QThread.

    This avoids native PySide/QThread construction crashes on Windows while
    preserving queued Qt signal delivery into the UI thread.
    """

    event_received = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, base_url: str, token: str | None = None, *, http_client: Any = None) -> None:
        super().__init__()
        self.base_url = base_url
        self.token = token
        self.http_client = http_client
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._source = None

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self.run,
                name="BridgeTracerSSEStreamWorker",
                daemon=True,
            )
            self._thread.start()

    def isRunning(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def run(self) -> None:
        try:
            source = SSEEventSource(
                self.base_url,
                self.token,
                http_client=self.http_client,
                timeout=1.0,
            )
        except TypeError:
            source = SSEEventSource(
                self.base_url,
                self.token,
                http_client=self.http_client,
            )
        except Exception as exc:
            if not self._stop_event.is_set():
                self.error_occurred.emit(str(exc))
            return

        self._source = source
        try:
            with source:
                for msg in source:
                    if self._stop_event.is_set():
                        break

                    if msg.event not in ("trace", "snapshot") or not msg.data:
                        continue

                    try:
                        data = json.loads(msg.data)
                    except Exception:
                        continue

                    if self._stop_event.is_set():
                        break

                    if isinstance(data, list):
                        for item in data:
                            if self._stop_event.is_set():
                                break
                            if isinstance(item, dict):
                                self.event_received.emit(item)
                    elif isinstance(data, dict):
                        self.event_received.emit(data)

        except Exception as exc:
            if not self._stop_event.is_set():
                self.error_occurred.emit(str(exc))
        finally:
            self._source = None

    def stop(self) -> None:
        self._stop_event.set()

        # Do not close self._source from the GUI thread. Let the worker thread
        # own and exit its own httpx/SSE stream lifetime.
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)


@dataclass(frozen=True)
class ControllerStatus:
    connected: bool = False
    label: str = "token/auth: unknown - disconnected"
    safe_description: str = ""
    recording_state: RecordingState = RecordingState.IDLE


class BridgeTracerController(QObject):
    def __init__(self, *, client_factory: Callable[..., BridgeClient] = BridgeClient) -> None:
        super().__init__()
        self._client_factory = client_factory
        self._client = None
        self._recorder = Recorder(on_state_change=self._on_recording_state_change)
        self._events: list[EventModel] = []
        self._seen_ids: set[str] = set()
        self.status = ControllerStatus()
        self._worker: SSEStreamWorker | None = None
        self._worker_http_client = None
        self._log_fallback = False

    @property
    def events(self) -> list[EventModel]:
        if self._recorder.events:
            return self._recorder.sorted_events()
        return list(self._events)

    @property
    def is_log_fallback(self) -> bool:
        return self._log_fallback

    def set_events(self, events: list[EventModel]) -> None:
        """Seed the controller's standing events (used when the UI is opened
        with sample/loaded data before any live recording)."""
        self._events = list(events)

    def connect(self, base_url: str, token: str | None = None) -> ControllerStatus:
        token = token or _env_auth_token()
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
        self._log_fallback = False
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
        event_id = self._raw_event_id(raw_evt)
        if event_id and event_id in self._seen_ids:
            return
        event = self._recorder.feed(raw_evt)
        if event is not None:
            self._seen_ids.add(event.id)

    def _stop_stream_worker(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            try:
                try:
                    worker.event_received.disconnect(self._on_stream_event)
                except Exception:
                    pass
                worker.stop()
            except Exception:
                pass

    def _raw_event_id(self, raw: Any) -> str | None:
        if isinstance(raw, EventModel):
            return raw.id
        if isinstance(raw, dict):
            for key in ("id", "event_id", "uuid"):
                value = raw.get(key)
                if value:
                    return str(value)
        return None

    def start_recording(self) -> None:
        if self._client is None:
            self.connect(os.environ.get("AI_BRIDGE_URL", "http://127.0.0.1:8765"), _env_auth_token())

        if self._recorder.state == RecordingState.STOPPED:
            self._recorder = Recorder(
                on_state_change=self._on_recording_state_change,
                on_stop_subscriptions=self._stop_stream_worker
            )
        else:
            self._recorder._on_stop_subscriptions = self._stop_stream_worker

        self._seen_ids = set()
        self._log_fallback = False
        self._recorder.start()

        if self.trace_available():
            base_url = self._client._base_url if hasattr(self._client, "_base_url") else ""
            token = self._client._token if hasattr(self._client, "_token") else None
            self._worker = SSEStreamWorker(
                base_url=base_url,
                token=token,
                http_client=self._worker_http_client
            )
            self._worker.event_received.connect(self._on_stream_event, Qt.QueuedConnection)
            self._worker.start()
        elif _log_fallback_enabled():
            self._log_fallback = True

        self._on_recording_state_change(RecordingState.IDLE, self._recorder.state)

    def pull_once(self, *, since: str | None = None) -> int:
        if self._client is None:
            return 0
        return self._recorder.feed_many(self._client.list_events(since=since))

    def pull_logs(self, *, limit: int | None = 500) -> int:
        """Poll /logs only when explicit log fallback is enabled.

        Normal recording is strictly SSE. /logs is a fallback transport only,
        activated by AI_BRIDGE_RECORDING_FALLBACK=logs when SSE is unavailable.
        """
        if (
            self._client is None
            or self._recorder.state != RecordingState.RECORDING
            or not self._log_fallback
        ):
            return 0
        raw_events = self._client.fetch_logs(limit=limit)
        new_count = 0
        for raw in raw_events:
            event_id = self._raw_event_id(raw)
            if event_id and event_id in self._seen_ids:
                continue
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
        self._log_fallback = False
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
