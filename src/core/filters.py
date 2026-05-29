"""Pre-record and post-record filters (BridgeTracer.md §3 and §5).

Both filters share the same selector vocabulary so the UI can convert a
single Filter form into either flavour without duplicating the spec. The
distinction is *when* they apply:

    pre-record  — runs inside Recorder.feed(). Events that fail the filter
                  are never stored or persisted. Use to reduce noise + size.

    post-record — runs in the UI layer over an already-recorded list. Pure
                  function; the saved recording is untouched, the filter can
                  be toggled freely.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .schemas import EventCategory, EventLevel, EventModel


def _to_str_set(values: Optional[Iterable[str]]) -> set[str]:
    if values is None:
        return set()
    out: set[str] = set()
    for v in values:
        if hasattr(v, "value"):
            out.add(str(v.value).lower())
        else:
            out.add(str(v).lower())
    return out


@dataclass
class _BaseFilter:
    categories: Optional[Iterable[EventCategory | str]] = None
    types: Optional[Iterable[str]] = None
    session_ids: Optional[Iterable[str]] = None
    request_ids: Optional[Iterable[str]] = None
    run_ids: Optional[Iterable[str]] = None
    levels: Optional[Iterable[EventLevel | str]] = None
    text_search: Optional[str] = None
    min_duration_ms: Optional[float] = None
    max_duration_ms: Optional[float] = None
    require_file_refs: bool = False
    require_tool_calls: bool = False

    def _normalized(self) -> dict[str, set[str]]:
        return {
            "categories": _to_str_set(self.categories),
            "types": _to_str_set(self.types),
            "session_ids": _to_str_set(self.session_ids),
            "request_ids": _to_str_set(self.request_ids),
            "run_ids": _to_str_set(self.run_ids),
            "levels": _to_str_set(self.levels),
        }

    def matches(self, event: EventModel) -> bool:
        n = self._normalized()

        if n["categories"] and str(event.category.value).lower() not in n["categories"]:
            return False
        if n["types"] and str(event.type).lower() not in n["types"]:
            return False
        if n["session_ids"] and str(event.session_id or "").lower() not in n["session_ids"]:
            return False
        if n["request_ids"] and str(event.request_id or "").lower() not in n["request_ids"]:
            return False
        if n["run_ids"] and str(event.run_id or "").lower() not in n["run_ids"]:
            return False
        if n["levels"] and str(event.level.value).lower() not in n["levels"]:
            return False

        if self.text_search:
            needle = self.text_search.lower()
            if not _matches_text(event, needle):
                return False

        if self.min_duration_ms is not None:
            if event.duration_ms is None or event.duration_ms < self.min_duration_ms:
                return False
        if self.max_duration_ms is not None:
            if event.duration_ms is None or event.duration_ms > self.max_duration_ms:
                return False

        if self.require_file_refs and not event.refs:
            return False
        if self.require_tool_calls and event.category != EventCategory.TOOL:
            return False

        return True

    def to_dict(self) -> dict:
        return {
            "categories": sorted(_to_str_set(self.categories)),
            "types": sorted(_to_str_set(self.types)),
            "session_ids": sorted(_to_str_set(self.session_ids)),
            "request_ids": sorted(_to_str_set(self.request_ids)),
            "run_ids": sorted(_to_str_set(self.run_ids)),
            "levels": sorted(_to_str_set(self.levels)),
            "text_search": self.text_search,
            "min_duration_ms": self.min_duration_ms,
            "max_duration_ms": self.max_duration_ms,
            "require_file_refs": self.require_file_refs,
            "require_tool_calls": self.require_tool_calls,
        }


@dataclass
class PreRecordFilter(_BaseFilter):
    """Subscription filter — events that don't match are never recorded."""


@dataclass
class PostRecordFilter(_BaseFilter):
    """View filter — applied over a finished recording without mutating it."""


def _matches_text(event: EventModel, needle: str) -> bool:
    """Case-insensitive substring across summary, type, and the JSON dump of details."""
    if needle in (event.summary or "").lower():
        return True
    if needle in (event.type or "").lower():
        return True
    if event.details:
        try:
            import json
            if needle in json.dumps(event.details, default=str).lower():
                return True
        except Exception:
            pass
    return False


def apply_post_filter(events: Iterable[EventModel], flt: PostRecordFilter) -> list[EventModel]:
    """Pure-function reducer for the UI's filter chips. Never mutates the input."""
    return [e for e in events if flt.matches(e)]


__all__ = [
    "PreRecordFilter",
    "PostRecordFilter",
    "apply_post_filter",
]
