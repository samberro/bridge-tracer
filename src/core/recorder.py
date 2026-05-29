"""Recording session lifecycle.

Mirrors BridgeTracer.md §2 "Recording Session Control" precisely:

    idle → recording → stopping → stopped
                                ↘ failed

Critical guarantees the plan calls out:

    * Stop must close stream subscriptions cleanly.
    * Stop must flush buffered events (no event loss after stop is pressed).
    * Stop must mark recording_end_time.
    * Stop must trigger post-record tasks (file-ref retrieval is the obvious
      one, but the recorder doesn't *do* the retrieval — it only signals).
    * Stop must be testable outside the UI.

The recorder is intentionally synchronous-friendly. Streams and timers live
elsewhere; this class just enforces the state machine and aggregates events.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

from .events import normalize_event, sort_events, validate_event_dict
from .schemas import EventModel, RecordingMetadata, RecordingState


class RecorderError(RuntimeError):
    """Raised when the recorder is asked to do something invalid for its state."""


_ALLOWED: dict[RecordingState, set[RecordingState]] = {
    RecordingState.IDLE: {RecordingState.RECORDING, RecordingState.FAILED},
    RecordingState.RECORDING: {RecordingState.STOPPING, RecordingState.FAILED},
    RecordingState.STOPPING: {RecordingState.STOPPED, RecordingState.FAILED},
    RecordingState.STOPPED: set(),
    RecordingState.FAILED: set(),
}


class Recorder:
    """A single recording session.

    Composed (not subclassed) — wire it into bridge_client, file_refs, and
    storage in `app/`.  Callbacks fire synchronously; the UI layer is
    responsible for marshalling them onto its event loop.
    """

    def __init__(
        self,
        *,
        prefilter: Optional[Callable[[EventModel], bool]] = None,
        on_event: Optional[Callable[[EventModel], None]] = None,
        on_state_change: Optional[Callable[[RecordingState, RecordingState], None]] = None,
        on_stop_subscriptions: Optional[Callable[[], None]] = None,
        on_post_record: Optional[Callable[[list[EventModel]], None]] = None,
    ) -> None:
        self._state = RecordingState.IDLE
        self._events: list[EventModel] = []
        self._buffer: list[EventModel] = []
        self._metadata = RecordingMetadata(state=RecordingState.IDLE)

        self._prefilter = prefilter
        self._on_event = on_event
        self._on_state_change = on_state_change
        self._on_stop_subscriptions = on_stop_subscriptions
        self._on_post_record = on_post_record

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    @property
    def state(self) -> RecordingState:
        return self._state

    @property
    def metadata(self) -> RecordingMetadata:
        return self._metadata

    @property
    def events(self) -> list[EventModel]:
        return list(self._events)

    def _transition(self, target: RecordingState) -> None:
        if target not in _ALLOWED.get(self._state, set()):
            raise RecorderError(f"illegal transition: {self._state.value} → {target.value}")
        previous = self._state
        self._state = target
        self._metadata = self._metadata.model_copy(update={"state": target})
        if self._on_state_change:
            self._on_state_change(previous, target)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self, *, active_filters: Optional[dict[str, Any]] = None,
              active_triggers: Optional[dict[str, Any]] = None) -> None:
        """Move IDLE → RECORDING. Marks `started_at` and stamps the metadata
        with the filters/triggers active at the moment of start.
        """
        if self._state != RecordingState.IDLE:
            raise RecorderError(f"start() requires IDLE state, current={self._state.value}")
        now = datetime.now(timezone.utc)
        self._metadata = self._metadata.model_copy(update={
            "started_at": now,
            "active_filters": dict(active_filters or {}),
            "active_triggers": dict(active_triggers or {}),
        })
        self._transition(RecordingState.RECORDING)

    def feed(self, raw: Any) -> Optional[EventModel]:
        """Push a single event in. Returns the normalized event if accepted,
        None if it was dropped by the pre-record filter or by being malformed.
        Malformed events themselves are recorded as a synthetic `parser`
        event by the caller — the recorder doesn't fabricate.
        """
        if self._state == RecordingState.STOPPED:
            raise RecorderError("recorder is already stopped")
        if self._state in (RecordingState.IDLE, RecordingState.FAILED):
            # The plan says we mustn't lose events that are "already received"
            # at stop time. Events that arrive before start, or after fail,
            # are dropped intentionally — the user explicitly asked not to record.
            return None

        event, err = validate_event_dict(raw)
        if event is None:
            return None  # caller's responsibility to emit a synthetic parser event

        if self._prefilter is not None and not self._prefilter(event):
            return None

        # During RECORDING events go straight onto the live list. During
        # STOPPING we buffer until the explicit flush at the end of stop().
        # The buffer guarantees no event loss between "stop requested" and
        # "subscriptions actually closed".
        if self._state == RecordingState.STOPPING:
            self._buffer.append(event)
        else:
            self._events.append(event)
            if self._on_event:
                self._on_event(event)

        return event

    def feed_many(self, events: Iterable[Any]) -> int:
        count = 0
        for raw in events:
            if self.feed(raw) is not None:
                count += 1
        return count

    def stop(self) -> RecordingMetadata:
        """Move RECORDING → STOPPING → STOPPED with the contractually correct
        order:

            1. enter STOPPING (so any in-flight feed() goes to the buffer)
            2. close subscriptions (on_stop_subscriptions hook)
            3. flush buffered events onto the live list
            4. stamp stopped_at + duration + event_count
            5. enter STOPPED
            6. run post-record hook
        """
        if self._state == RecordingState.IDLE:
            raise RecorderError("stop() requires RECORDING, current=idle")
        if self._state == RecordingState.STOPPED:
            return self._metadata
        if self._state == RecordingState.FAILED:
            raise RecorderError("stop() refused: recorder is in FAILED state")

        if self._state == RecordingState.RECORDING:
            self._transition(RecordingState.STOPPING)

        if self._on_stop_subscriptions is not None:
            try:
                self._on_stop_subscriptions()
            except Exception:
                # Subscription close failure must not lose buffered events.
                pass

        # Flush buffered events. Notify on_event for each so downstream
        # consumers see them too.
        flushed, self._buffer = self._buffer, []
        for evt in flushed:
            self._events.append(evt)
            if self._on_event:
                self._on_event(evt)

        now = datetime.now(timezone.utc)
        started = self._metadata.started_at
        duration_ms: float | None = None
        if started is not None:
            duration_ms = max(0.0, (now - started).total_seconds() * 1000.0)

        self._metadata = self._metadata.model_copy(update={
            "stopped_at": now,
            "duration_ms": duration_ms,
            "event_count": len(self._events),
        })
        self._transition(RecordingState.STOPPED)

        if self._on_post_record is not None:
            self._on_post_record(self.events)

        return self._metadata

    def fail(self, reason: str = "") -> RecordingMetadata:
        """Force a transition to FAILED. Useful when the bridge stream errors
        out without a clean stop. Closes subscriptions but does *not* run the
        post-record hook (that would lie about a clean recording).
        """
        if self._state == RecordingState.FAILED:
            return self._metadata
        previous_state = self._state
        # Stamp first so the metadata mutation is visible from the
        # on_state_change callback that runs inside _transition.
        self._metadata = self._metadata.model_copy(update={
            "notes": reason or self._metadata.notes,
        })
        # Force-transition (FAILED is reachable from any non-stopped state).
        self._state = RecordingState.FAILED
        self._metadata = self._metadata.model_copy(update={"state": RecordingState.FAILED})
        if previous_state != RecordingState.IDLE and self._on_stop_subscriptions is not None:
            try:
                self._on_stop_subscriptions()
            except Exception:
                pass
        if self._on_state_change:
            self._on_state_change(previous_state, RecordingState.FAILED)
        return self._metadata

    # ------------------------------------------------------------------
    # Convenience views
    # ------------------------------------------------------------------
    def sorted_events(self) -> list[EventModel]:
        return sort_events(self._events)
