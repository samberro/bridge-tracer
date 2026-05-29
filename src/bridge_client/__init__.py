"""Bearer-authed HTTP + SSE client for the bridge trace endpoints."""

from .client import BridgeClient, BridgeAPIError
from .stream import SSEEventSource, parse_sse_chunk

__all__ = ["BridgeClient", "BridgeAPIError", "SSEEventSource", "parse_sse_chunk"]
