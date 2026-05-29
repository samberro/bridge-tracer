"""Recording persistence (BridgeTracer.md §Phase 3 "Storage").

JSON for a whole-recording snapshot (events + metadata) and JSONL for
streaming/export. Loaded recordings re-validate every event so a corrupted
file never makes it into the timeline view as half-broken state.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from pydantic import ValidationError

from .events import normalize_event
from .schemas import EventModel, RecordingMetadata


class RecordingStorage:
    """Stateless save/load helpers — instantiate once and reuse."""

    @staticmethod
    def save_json(path: Path, metadata: RecordingMetadata, events: Iterable[EventModel]) -> Path:
        """Snapshot a recording to a single JSON file.

        Schema:
            {
              "metadata": { ...RecordingMetadata fields... },
              "events":   [ ...EventModel dicts in feed order... ]
            }
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "metadata": _model_dump(metadata),
            "events":   [_model_dump(e) for e in events],
        }
        path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
        return path

    @staticmethod
    def load_json(path: Path) -> tuple[RecordingMetadata, list[EventModel], list[str]]:
        """Load a JSON snapshot.

        Returns (metadata, events, errors). Events that fail revalidation are
        skipped with an entry pushed onto `errors` rather than raising — so a
        single corrupt event never poisons the whole recording.
        """
        path = Path(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        meta_raw = raw.get("metadata") or {}
        events_raw = raw.get("events") or []

        try:
            meta = RecordingMetadata.model_validate(meta_raw)
        except ValidationError as exc:
            raise ValueError(f"invalid recording metadata in {path}: {exc}") from exc

        events: list[EventModel] = []
        errors: list[str] = []
        for index, item in enumerate(events_raw):
            try:
                events.append(normalize_event(item))
            except (ValidationError, ValueError) as exc:
                errors.append(f"event[{index}]: {exc}")

        return meta, events, errors

    @staticmethod
    def save_jsonl(path: Path, events: Iterable[EventModel]) -> Path:
        """JSONL export — one event per line. The plan requires this for the
        "export JSONL" MVP item.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for evt in events:
                fh.write(json.dumps(_model_dump(evt), default=_json_default))
                fh.write("\n")
        return path

    @staticmethod
    def load_jsonl(path: Path) -> Iterator[EventModel]:
        path = Path(path)
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield normalize_event(json.loads(line))


def _model_dump(model) -> dict:
    # mode="json" so datetimes become ISO strings, enums become their .value, etc.
    return model.model_dump(mode="json")


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
