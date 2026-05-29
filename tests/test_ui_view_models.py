from __future__ import annotations

from src.core.schemas import EventCategory
from src.ui.sample_data import build_sample_events
from src.ui.view_models import (
    CATEGORY_LANES,
    TimelineViewModel,
    compare_event_details,
)


def test_timeline_view_model_groups_events_into_stable_lanes() -> None:
    model = TimelineViewModel(build_sample_events())

    lanes = model.lanes()

    assert list(lanes) == CATEGORY_LANES
    assert [event.summary for event in lanes[EventCategory.HTTP]][0] == "POST /api/send"
    assert any(event.type == "llm.response" for event in lanes[EventCategory.LLM])
    assert any(event.type == "tool.call" for event in lanes[EventCategory.TOOL])


def test_timeline_view_model_filters_without_mutating_recording() -> None:
    model = TimelineViewModel(build_sample_events())

    filtered = model.with_post_filter(categories={EventCategory.ERROR})

    assert len(model.events) > len(filtered.events)
    assert {event.category for event in filtered.events} == {EventCategory.ERROR}
    assert model.selected_event is not None


def test_timeline_view_model_selected_detail_is_inspector_ready() -> None:
    model = TimelineViewModel(build_sample_events())
    model.select_event("evt_llm_response")

    detail = model.selected_detail()

    assert detail is not None
    assert detail.title == "LLM response received"
    assert detail.badges == ["LLM", "info"]
    assert detail.fields["run_id"] == "run_8f31b2"
    assert "role" in detail.raw_json
    assert any("parent:" in item for item in detail.related)


def test_compare_event_details_reports_changed_payload_fields() -> None:
    events = build_sample_events()
    first = next(event for event in events if event.id == "evt_llm_request")
    second = next(event for event in events if event.id == "evt_llm_response")

    changes = compare_event_details(first, second)

    assert changes["type"] == ("llm.request", "llm.response")
    assert changes["summary"] == ("LLM request sent", "LLM response received")
    assert "level" not in changes
