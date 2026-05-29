"""Tests for src/core/auth.py — header building + token redaction."""
from __future__ import annotations

from src.core.auth import build_auth_headers, redact_token


def test_build_headers_includes_bearer_when_token_set():
    h = build_auth_headers("abc.def")
    assert h["Authorization"] == "Bearer abc.def"
    assert h["Accept"] == "application/json"


def test_build_headers_omits_authorization_when_no_token():
    h = build_auth_headers(None)
    assert "Authorization" not in h


def test_build_headers_includes_extra_headers():
    h = build_auth_headers("t", extra={"X-Trace": "yes"})
    assert h["X-Trace"] == "yes"


def test_redact_token_replaces_exact_token_in_string():
    assert redact_token("Authorization: Bearer abc.def", "abc.def") == \
           "Authorization: Bearer ***REDACTED***"


def test_redact_token_redacts_in_nested_dict():
    payload = {"headers": {"Authorization": "Bearer secret-xyz"}, "msg": "ok"}
    out = redact_token(payload, "secret-xyz")
    assert out["headers"]["Authorization"] == "Bearer ***REDACTED***"
    assert out["msg"] == "ok"


def test_redact_token_redacts_inside_list_and_tuple():
    payload = ["a", "Bearer secret", ("nested", "secret")]
    out = redact_token(payload, "secret")
    assert out == ["a", "Bearer ***REDACTED***", ("nested", "***REDACTED***")]


def test_redact_token_noop_on_empty_token():
    payload = {"Authorization": "Bearer secret-xyz"}
    assert redact_token(payload, None) == payload
    assert redact_token(payload, "") == payload


def test_redact_token_handles_unknown_token_via_bearer_pattern():
    """Even when we don't know the exact token, Bearer-pattern fallback wins."""
    out = redact_token({"h": "Bearer mystery-token-123"}, "different-token")
    assert out["h"] == "Bearer ***REDACTED***"


def test_redact_token_preserves_non_strings():
    payload = {"port": 9090, "active": True, "data": None}
    out = redact_token(payload, "tok")
    assert out == payload
