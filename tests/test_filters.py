"""Tests for src/core/filters.py."""
from __future__ import annotations

from src.core.events import normalize_event
from src.core.filters import PostRecordFilter, PreRecordFilter, apply_post_filter
from src.core.schemas import EventCategory, EventLevel, FileRef


def _evt(**kw):
    base = dict(type="http.request", category="http")
    base.update(kw)
    return normalize_event(base)


def test_empty_filter_matches_everything():
    flt = PreRecordFilter()
    assert flt.matches(_evt()) is True
    assert flt.matches(_evt(type="llm.request", category="llm")) is True


def test_category_filter_includes_only_matching():
    flt = PreRecordFilter(categories=[EventCategory.HTTP, "tool"])
    assert flt.matches(_evt(category="http")) is True
    assert flt.matches(_evt(category="tool")) is True
    assert flt.matches(_evt(category="llm")) is False


def test_type_and_text_search_filter():
    flt = PreRecordFilter(types=["llm.request"], text_search="lm studio")
    assert flt.matches(_evt(type="llm.request", category="llm",
                            summary="Sent chat completion request to LM Studio")) is True
    assert flt.matches(_evt(type="llm.response", category="llm",
                            summary="Sent chat completion request to LM Studio")) is False
    assert flt.matches(_evt(type="llm.request", category="llm",
                            summary="Sent something else")) is False


def test_session_and_request_and_run_id_filters():
    flt = PreRecordFilter(
        session_ids=["s1"], request_ids=["r1"], run_ids=["run1"],
    )
    assert flt.matches(_evt(session_id="s1", request_id="r1", run_id="run1")) is True
    assert flt.matches(_evt(session_id="s2", request_id="r1", run_id="run1")) is False


def test_level_filter():
    flt = PreRecordFilter(levels=[EventLevel.ERROR, "warning"])
    assert flt.matches(_evt(level="error")) is True
    assert flt.matches(_evt(level="warning")) is True
    assert flt.matches(_evt(level="info")) is False


def test_duration_filter_excludes_missing_durations():
    flt = PreRecordFilter(min_duration_ms=100.0)
    assert flt.matches(_evt(duration_ms=150.0)) is True
    assert flt.matches(_evt(duration_ms=50.0)) is False
    # Events with no duration are excluded once any duration bound is set.
    assert flt.matches(_evt()) is False


def test_max_duration_filter():
    flt = PreRecordFilter(max_duration_ms=200.0)
    assert flt.matches(_evt(duration_ms=200.0)) is True
    assert flt.matches(_evt(duration_ms=201.0)) is False


def test_require_file_refs_only_keeps_events_with_refs():
    flt = PreRecordFilter(require_file_refs=True)
    with_refs = _evt(refs=[{"ref_id": "f1", "path": "a.txt"}])
    without = _evt()
    assert flt.matches(with_refs) is True
    assert flt.matches(without) is False


def test_require_tool_calls_only_keeps_tool_category():
    flt = PreRecordFilter(require_tool_calls=True)
    assert flt.matches(_evt(category="tool")) is True
    assert flt.matches(_evt(category="llm")) is False


def test_apply_post_filter_returns_new_list_without_mutating_input():
    events = [
        _evt(category="http", type="http.request"),
        _evt(category="llm", type="llm.request"),
        _evt(category="tool", type="tool.run"),
    ]
    flt = PostRecordFilter(categories=["http", "tool"])
    filtered = apply_post_filter(events, flt)
    assert [e.type for e in filtered] == ["http.request", "tool.run"]
    # original list untouched
    assert len(events) == 3


def test_filter_text_search_walks_details_json():
    flt = PostRecordFilter(text_search="config.py")
    evt = _evt(details={"tool_args": {"path": "config.py"}}, category="tool")
    assert flt.matches(evt) is True


def test_filter_to_dict_is_serializable():
    flt = PreRecordFilter(
        categories=[EventCategory.HTTP],
        levels=[EventLevel.WARNING],
        min_duration_ms=50.0,
    )
    d = flt.to_dict()
    assert d["categories"] == ["http"]
    assert d["levels"] == ["warning"]
    assert d["min_duration_ms"] == 50.0
