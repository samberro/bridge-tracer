"""Tests for src/core/file_refs.py — limits, truncation, failure events."""
from __future__ import annotations

import pytest

from src.core.file_refs import FileRefLimits, FileRefRetriever
from src.core.schemas import FileRef


def _ref(ref_id="f1", path="a.txt"):
    return FileRef(ref_id=ref_id, path=path)


def test_text_file_under_inline_cap_is_fully_retrieved():
    def fetch(ref):
        return "text/plain", 11, "hello world"
    r = FileRefRetriever(fetch)
    result = r.retrieve([_ref()])
    assert result.events == []
    assert result.refs[0].retrieved is True
    assert result.refs[0].truncated is False
    assert result.refs[0].content_preview == "hello world"


def test_text_file_over_inline_cap_is_truncated():
    big = "x" * 200_000
    def fetch(ref):
        return "text/plain", len(big), big
    r = FileRefRetriever(fetch, FileRefLimits(max_inline_text_chars=100))
    result = r.retrieve([_ref()])
    assert result.refs[0].truncated is True
    assert len(result.refs[0].content_preview) == 100


def test_binary_file_has_no_inline_preview():
    def fetch(ref):
        return "application/octet-stream", 10, b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09"
    r = FileRefRetriever(fetch)
    result = r.retrieve([_ref()])
    assert result.refs[0].retrieved is True
    assert result.refs[0].content_preview is None


def test_per_ref_size_limit_emits_failure_event():
    def fetch(ref):
        return "text/plain", 10 * 1024 * 1024, "..."
    r = FileRefRetriever(fetch, FileRefLimits(max_file_bytes_per_ref=1 * 1024 * 1024))
    result = r.retrieve([_ref()])
    assert result.refs[0].retrieved is False
    assert result.refs[0].error == "per_ref_limit_exceeded"
    assert len(result.events) == 1
    assert result.events[0].type == "file.ref.retrieve_failed"


def test_total_cap_stops_subsequent_retrievals():
    def fetch(ref):
        return "text/plain", 3 * 1024 * 1024, "..."
    r = FileRefRetriever(fetch, FileRefLimits(
        max_file_bytes_per_ref=10 * 1024 * 1024,
        max_total_file_bytes=4 * 1024 * 1024,
    ))
    result = r.retrieve([_ref("a"), _ref("b")])
    assert result.refs[0].retrieved is True
    assert result.refs[1].retrieved is False
    assert result.refs[1].error == "total_limit_exceeded"
    assert any(e.type == "file.ref.retrieve_failed" for e in result.events)
    # Only the first ref's bytes count toward the total.
    assert result.total_bytes == 3 * 1024 * 1024


def test_fetcher_exception_creates_failure_event_and_error_record():
    def fetch(ref):
        raise RuntimeError("boom")
    r = FileRefRetriever(fetch)
    result = r.retrieve([_ref()])
    assert result.refs[0].retrieved is False
    assert "boom" in (result.refs[0].error or "")
    assert result.events and result.events[0].type == "file.ref.retrieve_failed"


def test_limits_default_match_plan():
    lim = FileRefLimits()
    assert lim.max_file_bytes_per_ref == 5 * 1024 * 1024
    assert lim.max_total_file_bytes == 50 * 1024 * 1024
    assert lim.max_inline_text_chars == 100_000
