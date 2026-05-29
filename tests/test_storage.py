"""Tests for src/core/storage.py — JSON snapshot + JSONL export round trips."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.events import normalize_event
from src.core.recorder import Recorder
from src.core.schemas import RecordingMetadata
from src.core.storage import RecordingStorage


def _make_recording(tmp_path):
    r = Recorder()
    r.start(active_filters={"categories": ["http", "llm"]}, active_triggers={"manual": True})
    r.feed({"type": "http.request", "category": "http", "summary": "GET /trace/events"})
    r.feed({"type": "llm.request", "category": "llm",
            "details": {"model": "gpt-4o", "prompt_tokens": 12}})
    r.stop()
    return r


def test_save_and_load_json_round_trip(tmp_path: Path):
    r = _make_recording(tmp_path)
    path = tmp_path / "rec.json"
    RecordingStorage.save_json(path, r.metadata, r.events)

    meta, events, errors = RecordingStorage.load_json(path)
    assert errors == []
    assert meta.event_count == 2
    assert meta.active_filters == {"categories": ["http", "llm"]}
    assert len(events) == 2
    assert events[0].type == "http.request"
    assert events[1].details["model"] == "gpt-4o"


def test_save_json_creates_parent_directory(tmp_path: Path):
    r = _make_recording(tmp_path)
    path = tmp_path / "nested" / "dir" / "rec.json"
    RecordingStorage.save_json(path, r.metadata, r.events)
    assert path.exists()


def test_jsonl_round_trip(tmp_path: Path):
    r = _make_recording(tmp_path)
    path = tmp_path / "rec.jsonl"
    RecordingStorage.save_jsonl(path, r.events)
    loaded = list(RecordingStorage.load_jsonl(path))
    assert len(loaded) == 2
    assert [e.type for e in loaded] == ["http.request", "llm.request"]


def test_load_json_collects_per_event_errors_without_raising(tmp_path: Path):
    payload = {
        "metadata": RecordingMetadata().model_dump(mode="json"),
        "events": [
            {"type": "good", "category": "http"},
            {"category": "http"},                # missing type
            {"type": "bad", "category": "not_a_category"},
            {"type": "another_good", "category": "llm"},
        ],
    }
    path = tmp_path / "partial.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    meta, events, errors = RecordingStorage.load_json(path)
    assert [e.type for e in events] == ["good", "another_good"]
    assert len(errors) == 2


def test_load_json_with_bad_metadata_raises(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({
        "metadata": {"event_count": -1},  # negative → invalid
        "events": [],
    }), encoding="utf-8")
    with pytest.raises(ValueError):
        RecordingStorage.load_json(path)


def test_load_jsonl_skips_blank_lines(tmp_path: Path):
    path = tmp_path / "rec.jsonl"
    path.write_text(
        "\n"
        + json.dumps(normalize_event({"type": "a", "category": "http"}).model_dump(mode="json"))
        + "\n\n"
        + json.dumps(normalize_event({"type": "b", "category": "http"}).model_dump(mode="json"))
        + "\n",
        encoding="utf-8",
    )
    loaded = list(RecordingStorage.load_jsonl(path))
    assert [e.type for e in loaded] == ["a", "b"]
