"""Event normalization + ordering helpers.

Separated from `schemas.py` so the model definitions stay pure data and the
transformation logic stays its own testable unit.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from pydantic import ValidationError

from .schemas import EventCategory, EventLevel, EventModel


def normalize_event(raw: Any) -> EventModel:
    """Turn a loose dict (or an EventModel) into a validated EventModel.

    Tolerates the most common bridge-side shape variations:
      - category given as the string form (e.g. "llm")
      - level missing (defaults to INFO)
      - timestamp missing (defaults to now)
      - id missing (auto-allocated)
    Raises pydantic.ValidationError on truly malformed input — callers should
    treat that as a `parser` event and continue.
    """
    if isinstance(raw, EventModel):
        return raw
    if not isinstance(raw, dict):
        raise ValueError(f"normalize_event expected dict, got {type(raw).__name__}")

    data = dict(raw)  # don't mutate caller's dict
    data.setdefault("level", EventLevel.INFO)
    data.setdefault("summary", "")
    data.setdefault("details", {})
    data.setdefault("refs", [])

    return EventModel.model_validate(data)


def validate_event_dict(raw: Any) -> tuple[EventModel | None, str | None]:
    """Non-raising variant: returns (event, None) on success, (None, msg) on failure."""
    try:
        return normalize_event(raw), None
    except (ValidationError, ValueError) as exc:
        return None, str(exc)


def sort_events(events: Iterable[EventModel]) -> list[EventModel]:
    """Chronological order, stable on id when timestamps tie.

    Note: stability matters for parent/child grouping during display, so we
    sort by (timestamp, id) rather than letting Python's default fallback to
    arbitrary ordering of model instances.
    """
    return sorted(events, key=lambda e: (_ts(e), e.id))


def _ts(event: EventModel) -> datetime:
    t = event.timestamp
    if t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc)
    return t


def group_by_request(events: Iterable[EventModel]) -> dict[str, list[EventModel]]:
    """Group events by request_id for timeline lane rendering. Events without
    a request_id are bucketed under the empty-string key so the caller can
    decide whether to render them inline or in a default lane.
    """
    groups: dict[str, list[EventModel]] = {}
    for evt in events:
        key = evt.request_id or ""
        groups.setdefault(key, []).append(evt)
    return groups


# Convenience re-exports so tests can import either from .schemas or .events.
__all__ = [
    "EventCategory",
    "EventLevel",
    "EventModel",
    "normalize_event",
    "validate_event_dict",
    "sort_events",
    "group_by_request",
]
