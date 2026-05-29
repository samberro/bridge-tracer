"""Recording start/stop triggers (BridgeTracer.md §4).

Triggers are business logic, not UI logic. They sit between the bridge
stream and the recorder; the UI just configures and observes them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Iterable, Optional

from .schemas import EventCategory, EventLevel, EventModel


@dataclass
class StartTrigger:
    """Decide whether an incoming event should start a recording.

    Multiple criteria can be combined; an event must satisfy *all* set
    criteria to fire (AND semantics). An empty StartTrigger matches anything,
    so callers should pair it with a manual-start gate in the UI.
    """
    endpoints: Optional[Iterable[str]] = None
    session_ids: Optional[Iterable[str]] = None
    request_ids: Optional[Iterable[str]] = None
    run_ids: Optional[Iterable[str]] = None
    event_types: Optional[Iterable[str]] = None
    on_warning_or_error: bool = False
    tool_names: Optional[Iterable[str]] = None
    llm_models: Optional[Iterable[str]] = None
    on_file_ref_created: bool = False

    def matches(self, event: EventModel) -> bool:
        if self.endpoints is not None:
            endpoint = str(event.details.get("endpoint", "") or "").lower()
            if endpoint not in {str(e).lower() for e in self.endpoints}:
                return False
        if self.session_ids is not None:
            if str(event.session_id or "").lower() not in {str(s).lower() for s in self.session_ids}:
                return False
        if self.request_ids is not None:
            if str(event.request_id or "").lower() not in {str(r).lower() for r in self.request_ids}:
                return False
        if self.run_ids is not None:
            if str(event.run_id or "").lower() not in {str(r).lower() for r in self.run_ids}:
                return False
        if self.event_types is not None:
            if str(event.type).lower() not in {str(t).lower() for t in self.event_types}:
                return False
        if self.on_warning_or_error and event.level not in (EventLevel.WARNING, EventLevel.ERROR):
            return False
        if self.tool_names is not None:
            tool = str(event.details.get("tool", "") or "").lower()
            if tool not in {str(t).lower() for t in self.tool_names}:
                return False
        if self.llm_models is not None:
            model = str(event.details.get("model", "") or "").lower()
            if model not in {str(m).lower() for m in self.llm_models}:
                return False
        if self.on_file_ref_created and event.type != "file.ref.created":
            return False
        return True


@dataclass
class StopTrigger:
    """Decide whether an incoming event (or counter) should stop a recording."""
    after_n_events: Optional[int] = None
    after_seconds: Optional[float] = None
    response_event_types: Optional[Iterable[str]] = None
    stop_on_error: bool = False
    on_request_or_run_completed: bool = False
    event_types: Optional[Iterable[str]] = None

    def matches(self, event: EventModel, *, recorded_count: int, elapsed_seconds: float) -> bool:
        if self.after_n_events is not None and recorded_count >= self.after_n_events:
            return True
        if self.after_seconds is not None and elapsed_seconds >= self.after_seconds:
            return True
        if self.response_event_types is not None:
            if str(event.type).lower() in {str(t).lower() for t in self.response_event_types}:
                return True
        if self.stop_on_error and event.level == EventLevel.ERROR:
            return True
        if self.on_request_or_run_completed and event.type.lower() in {
            "request.completed", "run.completed", "response.sent",
        }:
            return True
        if self.event_types is not None:
            if str(event.type).lower() in {str(t).lower() for t in self.event_types}:
                return True
        return False


class TriggerEvaluator:
    """Stateful glue around the start/stop trigger pair.

    Owns the "have we started yet?" flag and the start-time stamp used for
    the after_seconds stop trigger. Keeps the recorder dumb.
    """

    def __init__(self, start: Optional[StartTrigger], stop: Optional[StopTrigger],
                 *, time_fn=monotonic) -> None:
        self.start = start
        self.stop = stop
        self._time = time_fn
        self._started_at: float | None = None
        self._recorded_count = 0

    @property
    def started(self) -> bool:
        return self._started_at is not None

    def mark_started_manually(self) -> None:
        """Use when the user pressed Start Recording before any trigger fired."""
        if self._started_at is None:
            self._started_at = self._time()

    def consider_start(self, event: EventModel) -> bool:
        if self._started_at is not None:
            return False
        if self.start is None:
            return False
        if self.start.matches(event):
            self._started_at = self._time()
            return True
        return False

    def consider_stop(self, event: EventModel) -> bool:
        if self._started_at is None:
            return False
        self._recorded_count += 1
        elapsed = self._time() - self._started_at if self._started_at is not None else 0.0
        if self.stop is None:
            return False
        return self.stop.matches(event, recorded_count=self._recorded_count, elapsed_seconds=elapsed)
