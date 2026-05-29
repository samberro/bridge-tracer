"""Tests for src/core/triggers.py."""
from __future__ import annotations

import pytest

from src.core.events import normalize_event
from src.core.schemas import EventLevel
from src.core.triggers import StartTrigger, StopTrigger, TriggerEvaluator


def _evt(**kw):
    base = dict(type="http.request", category="http")
    base.update(kw)
    return normalize_event(base)


# ---- StartTrigger -----------------------------------------------------------
def test_start_trigger_endpoint_match():
    s = StartTrigger(endpoints=["/api/send"])
    assert s.matches(_evt(details={"endpoint": "/api/send"})) is True
    assert s.matches(_evt(details={"endpoint": "/api/other"})) is False


def test_start_trigger_session_or_request_id_match():
    s = StartTrigger(session_ids=["S1"], request_ids=["R1"])
    assert s.matches(_evt(session_id="S1", request_id="R1")) is True
    assert s.matches(_evt(session_id="S1", request_id="R2")) is False


def test_start_trigger_on_warning_or_error_only_fires_on_those_levels():
    s = StartTrigger(on_warning_or_error=True)
    assert s.matches(_evt(level=EventLevel.WARNING)) is True
    assert s.matches(_evt(level=EventLevel.ERROR)) is True
    assert s.matches(_evt(level=EventLevel.INFO)) is False


def test_start_trigger_tool_name_match():
    s = StartTrigger(tool_names=["read_file"])
    assert s.matches(_evt(category="tool", type="tool.call",
                          details={"tool": "read_file"})) is True
    assert s.matches(_evt(category="tool", type="tool.call",
                          details={"tool": "write_file"})) is False


def test_start_trigger_llm_model_match():
    s = StartTrigger(llm_models=["gpt-4o"])
    assert s.matches(_evt(category="llm", type="llm.request",
                          details={"model": "gpt-4o"})) is True
    assert s.matches(_evt(category="llm", details={"model": "claude"})) is False


def test_start_trigger_on_file_ref_created():
    s = StartTrigger(on_file_ref_created=True)
    assert s.matches(_evt(type="file.ref.created", category="file")) is True
    assert s.matches(_evt(type="file.ref.retrieved", category="file")) is False


# ---- StopTrigger ------------------------------------------------------------
def test_stop_trigger_after_n_events():
    s = StopTrigger(after_n_events=2)
    assert s.matches(_evt(), recorded_count=1, elapsed_seconds=0.0) is False
    assert s.matches(_evt(), recorded_count=2, elapsed_seconds=0.0) is True


def test_stop_trigger_after_seconds():
    s = StopTrigger(after_seconds=1.0)
    assert s.matches(_evt(), recorded_count=10, elapsed_seconds=0.9) is False
    assert s.matches(_evt(), recorded_count=10, elapsed_seconds=1.0) is True


def test_stop_trigger_on_response_event():
    s = StopTrigger(response_event_types=["llm.response"])
    assert s.matches(_evt(type="llm.response"), recorded_count=1, elapsed_seconds=0.0) is True
    assert s.matches(_evt(type="llm.request"), recorded_count=1, elapsed_seconds=0.0) is False


def test_stop_trigger_stop_on_error():
    s = StopTrigger(stop_on_error=True)
    assert s.matches(_evt(level=EventLevel.ERROR), recorded_count=1, elapsed_seconds=0.0) is True
    assert s.matches(_evt(level=EventLevel.INFO), recorded_count=1, elapsed_seconds=0.0) is False


def test_stop_trigger_request_or_run_completed():
    s = StopTrigger(on_request_or_run_completed=True)
    assert s.matches(_evt(type="request.completed"), recorded_count=1, elapsed_seconds=0.0) is True
    assert s.matches(_evt(type="run.completed"), recorded_count=1, elapsed_seconds=0.0) is True
    assert s.matches(_evt(type="something.else"), recorded_count=1, elapsed_seconds=0.0) is False


# ---- TriggerEvaluator (the stateful glue) -----------------------------------
def test_evaluator_consider_start_fires_once_then_no_op():
    ticks = iter([100.0, 101.0, 102.0])
    ev = TriggerEvaluator(
        StartTrigger(event_types=["llm.request"]),
        None,
        time_fn=lambda: next(ticks),
    )
    assert ev.started is False
    assert ev.consider_start(_evt(type="llm.request", category="llm")) is True
    assert ev.started is True
    # subsequent matching events shouldn't re-start
    assert ev.consider_start(_evt(type="llm.request", category="llm")) is False


def test_evaluator_mark_started_manually_sets_clock():
    ticks = iter([100.0, 105.0])
    ev = TriggerEvaluator(None, StopTrigger(after_seconds=2.0), time_fn=lambda: next(ticks))
    ev.mark_started_manually()
    assert ev.started is True
    # 5s elapsed > 2s → stop
    assert ev.consider_stop(_evt()) is True


def test_evaluator_consider_stop_only_after_start():
    ev = TriggerEvaluator(None, StopTrigger(stop_on_error=True))
    assert ev.consider_stop(_evt(level=EventLevel.ERROR)) is False
    ev.mark_started_manually()
    assert ev.consider_stop(_evt(level=EventLevel.ERROR)) is True
