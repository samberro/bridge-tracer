"""Bearer-auth header construction + token redaction (BridgeTracer.md §10).

The plan's strict rules:

    * never log token in event payloads
    * redact token if it appears in headers/logs

Both are enforced here so the bridge_client and the storage layer can call
them mechanically — nobody has to remember "did I redact?".
"""
from __future__ import annotations

import re
from typing import Any, Mapping

_REDACTED = "***REDACTED***"


def build_auth_headers(token: str | None, *, extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build the HTTP headers needed by the bridge.

    If `token` is empty/None the Authorization header is omitted — useful for
    the "first connect without credentials" probe in the UI.
    """
    headers: dict[str, str] = {"Accept": "application/json"}
    if extra:
        headers.update({str(k): str(v) for k, v in extra.items()})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def redact_token(payload: Any, token: str | None) -> Any:
    """Walk a JSON-shaped value and replace any occurrence of `token` with
    a fixed placeholder. Works on strings, dicts, lists, tuples.

    Empty/None token is a no-op (don't redact a *literal* empty string;
    that would mangle every empty value in the payload).
    """
    if not token:
        return payload
    return _redact(payload, str(token))


def _redact(value: Any, token: str) -> Any:
    if isinstance(value, str):
        return _redact_str(value, token)
    if isinstance(value, dict):
        return {k: _redact(v, token) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v, token) for v in value]
    if isinstance(value, tuple):
        return tuple(_redact(v, token) for v in value)
    return value


def _redact_str(s: str, token: str) -> str:
    # Exact-token substring redaction first (covers headers like
    # "Authorization: Bearer abc.def"). Then fall back to the common
    # "Bearer <opaque>" pattern in case the token itself was rotated and the
    # captured payload still has the prior value.
    if token in s:
        s = s.replace(token, _REDACTED)
    s = re.sub(r"(?i)Bearer\s+[A-Za-z0-9._\-]+", f"Bearer {_REDACTED}", s)
    return s
