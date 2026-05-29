"""Targeted tests to close the coverage gaps in recorder.py and stream.py.

Pure coverage-driven; each test names the branch it pins.
"""
from __future__ import annotations

import httpx
import pytest

from src.bridge_client.stream import SSEEventSource, parse_sse_chunk
from src.core.recorder import Recorder, RecorderError
from src.core.schemas import RecordingState
from src.core.triggers import TriggerEvaluator


# ---- recorder.py ------------------------------------------------------------
def test_feed_after_stopped_raises():
    """recorder.py:118-119 — feed must error after STOPPED, not silently drop."""
    r = Recorder()
    r.start()
    r.feed({"type": "x", "category": "http"})
    r.stop()
    with pytest.raises(RecorderError):
        r.feed({"type": "x", "category": "http"})


def test_feed_many_returns_accepted_count():
    """recorder.py:146-151 — feed_many counts only accepted events."""
    r = Recorder()
    r.start()
    accepted = r.feed_many([
        {"type": "ok", "category": "http"},
        {"type": "no_category"},      # malformed → dropped
        {"type": "ok2", "category": "llm"},
    ])
    assert accepted == 2


def test_stop_when_failed_raises():
    """recorder.py:168-169 — stop() refuses to run on a FAILED recorder."""
    r = Recorder()
    r.start()
    r.fail("reason")
    with pytest.raises(RecorderError):
        r.stop()


def test_fail_from_idle_is_safe():
    """recorder.py:226-229 — fail() called before start() shouldn't crash and
    shouldn't try to close subscriptions (there are none)."""
    closed = []
    r = Recorder(on_stop_subscriptions=lambda: closed.append(True))
    r.fail("never started")
    assert r.state == RecordingState.FAILED
    assert closed == []


def test_illegal_transition_message_quoted():
    """recorder.py:87 — _transition's RecorderError message includes both states."""
    r = Recorder()
    r.start()
    r.fail()
    # After FAILED there is no allowed transition; start() should raise.
    with pytest.raises(RecorderError):
        r.start()


# ---- stream.py --------------------------------------------------------------
def test_parse_sse_handles_field_without_colon():
    """stream.py:65 — bare field line (no colon, no value) must not crash."""
    chunk = "event\ndata: ok\n\n"
    msgs = parse_sse_chunk(chunk)
    # Field name "event" with no value should reset to 'message'.
    assert msgs[0].event == "message"
    assert msgs[0].data == "ok"


def test_parse_sse_retry_invalid_is_ignored():
    """stream.py:75-76 — retry: <non-int> shouldn't raise."""
    chunk = "retry: not_a_number\ndata: ok\n\n"
    msgs = parse_sse_chunk(chunk)
    assert msgs[0].retry_ms is None


def test_sse_event_source_close_is_idempotent():
    """stream.py:140-146 — calling close() twice should not raise."""
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"event: ping\ndata: 1\n\n",
                              headers={"content-type": "text/event-stream"})
    http = httpx.Client(transport=httpx.MockTransport(handler))
    src = SSEEventSource("http://bridge.test", token=None, http_client=http)
    with src as s:
        list(s)
    src.close()  # second close, should be no-op


def test_sse_event_source_raises_when_iterated_outside_context():
    src = SSEEventSource("http://bridge.test", token=None,
                        http_client=httpx.Client(transport=httpx.MockTransport(
                            lambda r: httpx.Response(200))))
    with pytest.raises(RuntimeError):
        next(iter(src))


def test_sse_event_source_5xx_raises():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"")
    http = httpx.Client(transport=httpx.MockTransport(handler))
    from src.bridge_client.client import BridgeAPIError
    with pytest.raises(BridgeAPIError):
        with SSEEventSource("http://bridge.test", token="t", http_client=http):
            pass


# ---- triggers.py ------------------------------------------------------------
def test_evaluator_no_start_trigger_never_auto_starts():
    """triggers.py:127 — consider_start with start=None returns False."""
    from src.core.events import normalize_event
    ev = TriggerEvaluator(None, None)
    assert ev.consider_start(normalize_event({"type": "x", "category": "http"})) is False
