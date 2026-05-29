"""SSE event stream client for /trace/events/stream.

We avoid taking a heavyweight SSE dependency — parsing per the SSE spec is a
few lines and lets the tests be hermetic. `SSEEventSource` is iterable so the
recorder loop in `app/` can just `for event in source: recorder.feed(event)`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional

import httpx

from ..core.auth import build_auth_headers
from .client import BridgeAPIError


@dataclass
class SSEMessage:
    event: str
    data: str
    id: Optional[str] = None
    retry_ms: Optional[int] = None

    def json(self):
        return json.loads(self.data) if self.data else None


def parse_sse_chunk(chunk: str) -> list[SSEMessage]:
    """Parse a chunk of SSE wire format into discrete messages.

    Per https://html.spec.whatwg.org/multipage/server-sent-events.html:
        - lines are LF-separated
        - blank line dispatches the current event
        - "field: value" with optional leading space on value
        - lines beginning with ":" are comments
    """
    messages: list[SSEMessage] = []
    event_type = "message"
    data_buf: list[str] = []
    last_id: Optional[str] = None
    retry: Optional[int] = None

    def flush():
        nonlocal event_type, data_buf
        if data_buf:
            messages.append(SSEMessage(
                event=event_type, data="\n".join(data_buf), id=last_id, retry_ms=retry,
            ))
        event_type = "message"
        data_buf = []

    for raw_line in chunk.splitlines():
        if raw_line == "":
            flush()
            continue
        if raw_line.startswith(":"):
            continue  # comment / keepalive
        if ":" in raw_line:
            field, _, value = raw_line.partition(":")
            if value.startswith(" "):
                value = value[1:]
        else:
            field, value = raw_line, ""
        if field == "event":
            event_type = value or "message"
        elif field == "data":
            data_buf.append(value)
        elif field == "id":
            last_id = value
        elif field == "retry":
            try:
                retry = int(value)
            except ValueError:
                retry = None

    flush()
    return messages


class SSEEventSource:
    """Stream wrapper around httpx.stream("GET", /trace/events/stream).

    Use as a context manager:

        with SSEEventSource(base_url, token) as src:
            for msg in src:
                recorder.feed(msg.json())

    Reconnection: the bridge can send a `retry: <ms>` field; the caller is
    responsible for honoring it. The plan calls for "clean disconnect on
    stop" which is just closing the source.
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        *,
        http_client: Optional[httpx.Client] = None,
        path: str = "/trace/events/stream",
        timeout: Optional[float] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._path = path if path.startswith("/") else f"/{path}"
        self._timeout = timeout
        self._http = http_client or httpx.Client(timeout=timeout)
        self._owns_http = http_client is None
        self._stream_ctx = None
        self._response = None
        self._closed = False

    def __enter__(self) -> "SSEEventSource":
        self._stream_ctx = self._http.stream(
            "GET", f"{self._base_url}{self._path}",
            headers={**build_auth_headers(self._token), "Accept": "text/event-stream"},
        )
        self._response = self._stream_ctx.__enter__()
        if self._response.status_code in (401, 403):
            raise BridgeAPIError(
                f"SSE auth failure ({self._response.status_code})",
                status=self._response.status_code,
            )
        if self._response.status_code >= 400:
            raise BridgeAPIError(f"SSE upstream error: {self._response.status_code}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._stream_ctx is not None:
            try:
                self._stream_ctx.__exit__(None, None, None)
            except Exception:
                pass
        if self._owns_http:
            try:
                self._http.close()
            except Exception:
                pass

    def __iter__(self) -> Iterator[SSEMessage]:
        if self._response is None:
            raise RuntimeError("SSEEventSource used outside its context manager")
        buffer = ""
        for chunk in self._response.iter_text():
            if self._closed:
                break
            if not chunk:
                continue
            buffer += chunk
            # Dispatch on blank-line boundaries; keep the trailing partial.
            while "\n\n" in buffer:
                block, _, buffer = buffer.partition("\n\n")
                for msg in parse_sse_chunk(block + "\n"):
                    yield msg

        # Flush any tail.
        if buffer.strip():
            for msg in parse_sse_chunk(buffer):
                yield msg


__all__ = ["SSEEventSource", "SSEMessage", "parse_sse_chunk"]
