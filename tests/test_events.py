"""Tests for src/core/events.py + src/core/schemas.py."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.core.events import (
    group_by_request,
    normalize_event,
    sort_events,
    validate_event_dict,
)
from src.core.schemas import EventCategory, EventLevel, EventModel, FileRef


def _evt(**kw):
    base = dict(type="http.request", category="http")
    base.update(kw)
    return base


def test_normalize_event_assigns_id_and_timestamp_when_missing():
    evt = normalize_event(_evt(summary="GET /trace/events"))
    assert evt.id.startswith("evt_")
    assert isinstance(evt.timestamp, datetime)
    assert evt.timestamp.tzinfo is not None
    assert evt.category == EventCategory.HTTP
    assert evt.level == EventLevel.INFO


def test_normalize_event_accepts_existing_id_and_timestamp_string():
    evt = normalize_event(_evt(id="evt_known", timestamp="2026-05-29T12:00:00Z"))
    assert evt.id == "evt_known"
    assert evt.timestamp.year == 2026
    assert evt.timestamp.tzinfo is not None


def test_normalize_event_coerces_unix_timestamp():
    evt = normalize_event(_evt(timestamp=1_716_990_000))
    assert evt.timestamp.year == 2024


def test_normalize_event_rejects_unknown_category():
    with pytest.raises(ValidationError):
        normalize_event(_evt(category="not_a_real_category"))


def test_normalize_event_rejects_non_dict_input():
    with pytest.raises(ValueError):
        normalize_event(["not", "a", "dict"])  # type: ignore[arg-type]


def test_normalize_event_pass_through_event_model():
    base = normalize_event(_evt())
    assert normalize_event(base) is base


def test_validate_event_dict_returns_error_message_on_bad_input():
    evt, err = validate_event_dict({"type": "x"})  # missing category
    assert evt is None
    assert err is not None
    assert "category" in err.lower()


def test_validate_event_dict_returns_event_on_good_input():
    evt, err = validate_event_dict(_evt())
    assert evt is not None and err is None


def test_sort_events_orders_by_timestamp_stably():
    a = normalize_event(_evt(id="evt_a", timestamp="2026-05-29T12:00:00Z"))
    b = normalize_event(_evt(id="evt_b", timestamp="2026-05-29T12:00:00Z"))
    c = normalize_event(_evt(id="evt_c", timestamp="2026-05-29T11:00:00Z"))
    ordered = sort_events([a, b, c])
    assert [e.id for e in ordered] == ["evt_c", "evt_a", "evt_b"]


def test_sort_events_handles_naive_timestamp():
    # Naive datetimes are treated as UTC for ordering, never crash.
    naive = EventModel.model_construct(
        id="evt_naive", type="x", category=EventCategory.HTTP,
        level=EventLevel.INFO, summary="", details={}, refs=[],
        timestamp=datetime(2026, 5, 29, 11, 30, 0),
    )
    aware = normalize_event(_evt(id="evt_aware", timestamp="2026-05-29T12:00:00Z"))
    ordered = sort_events([aware, naive])
    assert [e.id for e in ordered] == ["evt_naive", "evt_aware"]


def test_group_by_request_buckets_correctly():
    e1 = normalize_event(_evt(request_id="req_1"))
    e2 = normalize_event(_evt(request_id="req_1"))
    e3 = normalize_event(_evt(request_id="req_2"))
    e4 = normalize_event(_evt())  # no request_id
    groups = group_by_request([e1, e2, e3, e4])
    assert set(groups.keys()) == {"req_1", "req_2", ""}
    assert len(groups["req_1"]) == 2
    assert len(groups["req_2"]) == 1
    assert len(groups[""]) == 1


def test_event_model_allows_extra_fields():
    evt = normalize_event(_evt(custom_field="vendor_extension"))
    # extra="allow" — should be accessible
    assert getattr(evt, "custom_field", None) == "vendor_extension"


def test_event_model_file_refs_normalize():
    evt = normalize_event(_evt(refs=[{"ref_id": "f1", "path": "a.txt"}]))
    assert len(evt.refs) == 1
    assert isinstance(evt.refs[0], FileRef)
    assert evt.refs[0].ref_id == "f1"
