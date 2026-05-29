"""Tests for src/bridge_client/client.py and stream.py.

Uses httpx's MockTransport so we hit a deterministic backend without ever
opening a real socket.
"""
from __future__ import annotations

import json

import httpx
import pytest

from src.bridge_client.client import BridgeAPIError, BridgeClient
from src.bridge_client.stream import SSEEventSource, parse_sse_chunk


def _client(handler) -> BridgeClient:
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    return BridgeClient("http://bridge.test", token="t1", http_client=http)


# ---- HTTP client ------------------------------------------------------------
def test_list_events_sends_bearer_and_returns_list():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/trace/events"
        assert request.headers["Authorization"] == "Bearer t1"
        return httpx.Response(200, json=[{"id": "evt_1", "type": "http.request", "category": "http"}])

    c = _client(handler)
    events = c.list_events()
    assert events[0]["id"] == "evt_1"


def test_list_events_passes_since_cursor():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("since") == "evt_123"
        return httpx.Response(200, json=[])
    c = _client(handler)
    assert c.list_events(since="evt_123") == []


def test_auth_failure_raises_bridge_api_error_with_status():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="nope")
    c = _client(handler)
    with pytest.raises(BridgeAPIError) as exc_info:
        c.list_events()
    assert exc_info.value.status == 401


def test_5xx_raises_bridge_api_error():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")
    c = _client(handler)
    with pytest.raises(BridgeAPIError) as exc_info:
        c.list_runs()
    assert exc_info.value.status == 500


def test_network_failure_raises_bridge_api_error():
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down")
    c = _client(handler)
    with pytest.raises(BridgeAPIError):
        c.list_sessions()


def test_fetch_file_ref_returns_text_with_mime_and_size():
    body = b"hello world"
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/trace/file_refs/abc"
        return httpx.Response(200, content=body, headers={"content-type": "text/plain"})
    c = _client(handler)
    mime, size, data = c.fetch_file_ref("abc")
    assert mime == "text/plain"
    assert size == len(body)
    assert data == "hello world"


def test_fetch_file_ref_returns_bytes_for_binary_mime():
    body = b"\x00\x01\x02\x03"
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "application/octet-stream"})
    c = _client(handler)
    mime, size, data = c.fetch_file_ref("bin")
    assert mime == "application/octet-stream"
    assert data == body


def test_fetch_file_ref_auth_failure_surfaces():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")
    c = _client(handler)
    with pytest.raises(BridgeAPIError):
        c.fetch_file_ref("any")


def test_safe_describe_redacts_token():
    c = _client(lambda r: httpx.Response(200, json=[]))
    desc = c.safe_describe()
    assert "t1" not in desc["sample_headers"]
    assert "REDACTED" in desc["sample_headers"]
    assert desc["has_token"] == "yes"


def test_set_token_swaps_auth_header():
    captured = {}
    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=[])
    c = _client(handler)
    c.set_token("rotated")
    c.list_events()
    assert captured["auth"] == "Bearer rotated"


def test_bridge_client_context_manager_closes_http():
    """Smoke test that __enter__/__exit__ work with our context shape."""
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])
    with BridgeClient("http://bridge.test", token="t",
                      http_client=httpx.Client(transport=httpx.MockTransport(handler))) as c:
        assert c.list_events() == []


# ---- SSE parser -------------------------------------------------------------
def test_parse_sse_single_message():
    chunk = "event: ping\ndata: {\"a\": 1}\n\n"
    msgs = parse_sse_chunk(chunk)
    assert len(msgs) == 1
    assert msgs[0].event == "ping"
    assert msgs[0].json() == {"a": 1}


def test_parse_sse_multiline_data():
    chunk = "data: line1\ndata: line2\n\n"
    msgs = parse_sse_chunk(chunk)
    assert msgs[0].data == "line1\nline2"


def test_parse_sse_id_and_retry_fields():
    chunk = "id: 42\nretry: 1500\ndata: x\n\n"
    msgs = parse_sse_chunk(chunk)
    assert msgs[0].id == "42"
    assert msgs[0].retry_ms == 1500


def test_parse_sse_ignores_comments_and_keepalive():
    chunk = ": this is a comment\ndata: ok\n\n"
    msgs = parse_sse_chunk(chunk)
    assert msgs[0].data == "ok"


def test_parse_sse_two_messages_separated_by_blank_line():
    chunk = "event: a\ndata: 1\n\nevent: b\ndata: 2\n\n"
    msgs = parse_sse_chunk(chunk)
    assert [m.event for m in msgs] == ["a", "b"]
    assert [m.data for m in msgs] == ["1", "2"]


def test_parse_sse_message_json_returns_none_on_empty_data():
    chunk = "event: ping\n\n"
    msgs = parse_sse_chunk(chunk)
    # No data line means no message dispatched.
    assert msgs == []


def test_sse_event_source_yields_messages_from_mock_stream():
    """End-to-end SSE: mock httpx returns chunked SSE bytes, source yields parsed msgs."""
    body = (
        "event: ping\ndata: {\"x\": 1}\n\n"
        "event: tick\ndata: {\"x\": 2}\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/trace/events/stream"
        return httpx.Response(200, content=body.encode("utf-8"),
                              headers={"content-type": "text/event-stream"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with SSEEventSource("http://bridge.test", token="t", http_client=http) as src:
        msgs = list(src)

    assert [m.event for m in msgs] == ["ping", "tick"]
    assert msgs[0].json() == {"x": 1}


def test_sse_event_source_raises_on_auth_failure():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, content=b"")
    http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(BridgeAPIError):
        with SSEEventSource("http://bridge.test", token="t", http_client=http):
            pass
