from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from src.core.events import sort_events
from src.core.schemas import EventCategory, EventModel


CATEGORY_LANES = [
    EventCategory.HTTP,
    EventCategory.LLM,
    EventCategory.TOOL,
    EventCategory.FILE,
    EventCategory.PARSER,
    EventCategory.ERROR,
]


@dataclass(frozen=True)
class EventDetail:
    title: str
    badges: list[str]
    fields: dict[str, str]
    raw_json: str
    related: list[str]


class TimelineViewModel:
    def __init__(self, events: Iterable[EventModel], *, selected_event_id: str | None = None) -> None:
        self.events = sort_events(events)
        self.selected_event_id = selected_event_id or self._default_selected()

    @property
    def selected_event(self) -> EventModel | None:
        for event in self.events:
            if event.id == self.selected_event_id:
                return event
        return self.events[0] if self.events else None

    def _default_selected(self) -> str | None:
        for event in self.events:
            if event.type == "llm.response":
                return event.id
        return self.events[0].id if self.events else None

    def select_event(self, event_id: str) -> None:
        if any(event.id == event_id for event in self.events):
            self.selected_event_id = event_id

    def lanes(self) -> dict[EventCategory, list[EventModel]]:
        return {
            category: [event for event in self.events if event.category == category]
            for category in CATEGORY_LANES
        }

    def with_post_filter(self, *, categories: set[EventCategory] | None = None,
                         text: str | None = None) -> "TimelineViewModel":
        filtered = self.events
        if categories:
            filtered = [event for event in filtered if event.category in categories]
        if text:
            needle = text.casefold()
            filtered = [
                event for event in filtered
                if needle in event.summary.casefold() or needle in event.type.casefold()
            ]
        return TimelineViewModel(filtered, selected_event_id=self.selected_event_id)

    def selected_detail(self) -> EventDetail | None:
        event = self.selected_event
        if event is None:
            return None
        fields = {
            "timestamp": event.timestamp.isoformat().replace("+00:00", "Z"),
            "run_id": event.run_id or "",
            "session_id": event.session_id or "",
            "request_id": event.request_id or "",
        }
        if event.duration_ms is not None:
            fields["duration"] = _format_duration(event.duration_ms)
        for key in ("model", "tokens", "finish_reason"):
            if key in event.details:
                fields[key] = str(event.details[key])
        related = []
        if event.parent_event_id:
            related.append(f"parent: {event.parent_event_id}")
        related.extend(f"ref: {ref.path}" for ref in event.refs)
        for child in self.events:
            if child.parent_event_id == event.id:
                related.append(f"child: {child.summary}")
        return EventDetail(
            title=event.summary,
            badges=[event.category.value.upper(), event.level.value],
            fields=fields,
            raw_json=json.dumps(event.model_dump(mode="json"), indent=2),
            related=related,
        )


def compare_event_details(first: EventModel, second: EventModel) -> dict[str, tuple[str, str]]:
    first_payload = first.model_dump(mode="json")
    second_payload = second.model_dump(mode="json")
    changes: dict[str, tuple[str, str]] = {}
    for key in sorted(set(first_payload) | set(second_payload)):
        left = first_payload.get(key)
        right = second_payload.get(key)
        if left != right:
            changes[key] = (str(left), str(right))
    return changes


def _format_duration(ms: float) -> str:
    return f"{ms / 1000:.2f}s" if ms >= 1000 else f"{ms:.0f}ms"

