"""Map AI-Bridge ``/logs`` events onto the tracer's normalized EventModel.

The bridge does not expose ``/trace/events``; it emits LLM request/response
logs via ``GET /logs`` (and ``GET /logs/events`` SSE) shaped like::

    {
      "id": "log_<hex>", "created_at": "<iso8601>", "source": "llm",
      "direction": "input"|"output", "mode": "...", "request_id": "...",
      "session_id": "...", "run_id": "...", "status_code": 200, "ok": true,
      "payload": { ... }
    }

This adapter turns those into EventModel instances so the recorder/timeline can
ingest real bridge traffic.
"""
from __future__ import annotations

from typing import Any

from .schemas import EventCategory, EventLevel, EventModel


def _category_for(source: str) -> EventCategory:
    try:
        return EventCategory(source.lower())
    except ValueError:
        return EventCategory.SYSTEM


def _type_for(category: EventCategory, direction: str) -> str:
    direction = (direction or "").lower()
    if category == EventCategory.LLM:
        if direction == "input":
            return "llm.request"
        if direction == "output":
            return "llm.response"
        return "llm.event"
    base = category.value
    return f"{base}.{direction}" if direction else f"{base}.event"


def _level_for(raw: dict[str, Any]) -> EventLevel:
    if raw.get("ok") is False:
        return EventLevel.ERROR
    status = raw.get("status_code")
    if isinstance(status, int) and status >= 400:
        return EventLevel.ERROR
    return EventLevel.INFO


def _summary_for(category: EventCategory, direction: str, raw: dict[str, Any]) -> str:
    direction = (direction or "").lower()
    status = raw.get("status_code")
    if category == EventCategory.LLM:
        verb = {"input": "request sent", "output": "response received"}.get(direction, "event")
        mode = raw.get("mode")
        tail = f" ({mode})" if mode else ""
        if isinstance(status, int):
            tail += f" - {status}"
        return f"LLM {verb}{tail}"
    label = category.value
    if direction:
        label += f" {direction}"
    if isinstance(status, int):
        label += f" - {status}"
    return label


def map_log_event(raw: Any) -> EventModel:
    """Convert a single bridge log event dict into an EventModel.

    Raises ValueError if ``raw`` is not a dict so callers can record it as a
    parser failure rather than crashing the poll loop.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"bridge log event must be a dict, got {type(raw).__name__}")

    source = str(raw.get("source", "system"))
    direction = str(raw.get("direction", ""))
    category = _category_for(source)

    data: dict[str, Any] = {
        "type": _type_for(category, direction),
        "category": category,
        "level": _level_for(raw),
        "summary": _summary_for(category, direction, raw),
        "details": {
            k: v for k, v in raw.items()
            if k not in {"id", "created_at", "request_id", "session_id", "run_id"}
        },
        "request_id": raw.get("request_id"),
        "session_id": raw.get("session_id"),
        "run_id": raw.get("run_id"),
    }
    if raw.get("id"):
        data["id"] = str(raw["id"])
    if raw.get("created_at"):
        data["timestamp"] = raw["created_at"]

    return EventModel.model_validate(data)


def map_log_events(raws: Any) -> list[EventModel]:
    """Map a list of bridge log events, skipping malformed entries."""
    out: list[EventModel] = []
    for raw in (raws or []):
        try:
            out.append(map_log_event(raw))
        except Exception:
            continue
    return out
