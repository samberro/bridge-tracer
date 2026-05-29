"""Tests for src/core/recorder.py — lifecycle, prefilter, stop guarantees."""
from __future__ import annotations

import pytest

from src.core.recorder import Recorder, RecorderError
from src.core.schemas import RecordingState


def _evt(**kw):
    base = dict(type="http.request", category="http")
    base.update(kw)
    return base


def test_recorder_starts_in_idle():
    r = Recorder()
    assert r.state == RecordingState.IDLE
    assert r.metadata.state == RecordingState.IDLE


def test_start_requires_idle_state():
    r = Recorder()
    r.start()
    with pytest.raises(RecorderError):
        r.start()


def test_feed_before_start_is_dropped():
    r = Recorder()
    assert r.feed(_evt()) is None
    assert r.events == []


def test_happy_path_record_and_stop_marks_metadata():
    state_changes = []
    r = Recorder(on_state_change=lambda old, new: state_changes.append((old, new)))
    r.start(active_filters={"categories": ["http"]}, active_triggers={"manual": True})
    r.feed(_evt())
    r.feed(_evt(type="http.response"))
    meta = r.stop()
    assert r.state == RecordingState.STOPPED
    assert meta.event_count == 2
    assert meta.duration_ms is not None and meta.duration_ms >= 0
    assert meta.active_filters == {"categories": ["http"]}
    assert meta.active_triggers == {"manual": True}
    assert (RecordingState.IDLE, RecordingState.RECORDING) in state_changes
    assert (RecordingState.STOPPING, RecordingState.STOPPED) in state_changes


def test_stop_closes_subscriptions_before_flushing():
    order: list[str] = []
    def close_subs():
        order.append("close")
    def on_event(e):
        order.append(f"evt:{e.type}")
    def on_post(events):
        order.append("post")

    r = Recorder(
        on_event=on_event,
        on_stop_subscriptions=close_subs,
        on_post_record=on_post,
    )
    r.start()
    r.feed(_evt(type="http.request"))
    # Simulate an event arriving "during stop" — Recorder.feed pushes to buffer
    # while state is STOPPING. We force STOPPING by intercepting on_stop_subscriptions.
    def close_subs_with_buffered_event():
        order.append("close")
        # Feed during stop — this should land in buffer and flush after.
        r.feed(_evt(type="http.during_stop"))

    r2 = Recorder(on_event=on_event, on_stop_subscriptions=close_subs_with_buffered_event)
    r2.start()
    r2.feed(_evt(type="http.request"))
    r2.stop()
    types_in_order = [s for s in order if s.startswith("evt:") or s == "close"]
    # http.request was emitted live, then close, then http.during_stop flushed.
    assert types_in_order.index("evt:http.request") < types_in_order.index("close")
    assert types_in_order.index("close") < types_in_order.index("evt:http.during_stop")


def test_stop_runs_post_record_with_events():
    captured: list = []
    r = Recorder(on_post_record=lambda events: captured.extend(events))
    r.start()
    r.feed(_evt())
    r.stop()
    assert len(captured) == 1


def test_stop_when_idle_raises():
    r = Recorder()
    with pytest.raises(RecorderError):
        r.stop()


def test_stop_is_idempotent_after_stopped():
    r = Recorder()
    r.start()
    r.feed(_evt())
    meta1 = r.stop()
    meta2 = r.stop()  # should not raise, just return the same metadata
    assert meta1.event_count == meta2.event_count == 1


def test_subscription_close_failure_does_not_lose_buffered_events():
    def boom():
        raise RuntimeError("simulated stream close failure")
    r = Recorder(on_stop_subscriptions=boom)
    r.start()
    r.feed(_evt())
    meta = r.stop()
    assert meta.event_count == 1
    assert r.state == RecordingState.STOPPED


def test_prefilter_drops_unwanted_categories():
    def only_http(event):
        return event.category.value == "http"
    r = Recorder(prefilter=only_http)
    r.start()
    r.feed(_evt(type="http.request"))
    r.feed(_evt(type="llm.request", category="llm"))
    r.stop()
    assert len(r.events) == 1
    assert r.events[0].type == "http.request"


def test_malformed_event_is_dropped_silently():
    r = Recorder()
    r.start()
    # missing required field 'type'
    assert r.feed({"category": "http"}) is None
    assert r.feed("not a dict") is None
    r.stop()
    assert r.events == []


def test_fail_transitions_to_failed_and_closes_subscriptions():
    closed = []
    r = Recorder(on_stop_subscriptions=lambda: closed.append(True))
    r.start()
    r.fail("network reset")
    assert r.state == RecordingState.FAILED
    assert r.metadata.notes == "network reset"
    assert closed == [True]


def test_fail_is_idempotent():
    r = Recorder()
    r.start()
    r.fail("first")
    r.fail("second")  # no exception
    assert r.metadata.notes == "first"


def test_feed_after_fail_is_dropped():
    r = Recorder()
    r.start()
    r.fail()
    assert r.feed(_evt()) is None


def test_sorted_events_orders_by_timestamp():
    r = Recorder()
    r.start()
    r.feed(_evt(id="evt_b", timestamp="2026-05-29T12:00:00Z"))
    r.feed(_evt(id="evt_a", timestamp="2026-05-29T11:00:00Z"))
    r.stop()
    ordered = r.sorted_events()
    assert [e.id for e in ordered] == ["evt_a", "evt_b"]
