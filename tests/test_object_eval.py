from __future__ import annotations

import json
from datetime import datetime, timezone

from src.core.schemas import EventCategory, EventLevel, EventModel
from src.ui.render_rules import evaluate_expression, event_payload, path
from src.ui.interactive_window import InteractiveTracerWindow


def _llm_request_event() -> EventModel:
    return EventModel(
        id="evt_payload_text_json",
        type="llm.request",
        category=EventCategory.LLM,
        level=EventLevel.INFO,
        summary="LLM request sent",
        timestamp=datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc),
        details={
            "payload": {
                "text": json.dumps(
                    {
                        "model": "google/gemma-4-e2b",
                        "messages": [
                            {"role": "system", "content": "system setup"},
                            {"role": "user", "content": "why is it erroring in the image"},
                        ],
                    }
                )
            }
        },
    )


def test_event_payload_expands_payload_text_json() -> None:
    payload = event_payload(_llm_request_event())

    parsed = path(payload, "details.payload.text_json.messages[-1].content")

    assert parsed == "why is it erroring in the image"


def test_path_auto_descends_into_json_string_payload_text() -> None:
    payload = event_payload(_llm_request_event())

    parsed = path(payload, "details.payload.text.messages[-1].content")

    assert parsed == "why is it erroring in the image"


def test_eval_can_read_last_payload_message_from_text_json() -> None:
    result = evaluate_expression(
        "$.details.payload.text_json.messages[-1].content",
        _llm_request_event(),
    )

    assert result.ok is True
    assert result.text == "why is it erroring in the image"


def test_eval_can_read_last_payload_message_directly_from_text() -> None:
    result = evaluate_expression(
        "$.details.payload.text.messages[-1].content",
        _llm_request_event(),
    )

    assert result.ok is True
    assert result.text == "why is it erroring in the image"


def test_last_message_uses_payload_text_messages() -> None:
    result = evaluate_expression("last_message(obj)", _llm_request_event())

    assert result.ok is True
    assert result.text == "why is it erroring in the image"


class _TextBox:
    def __init__(self, value: str) -> None:
        self._value = value

    def text(self) -> str:
        return self._value


class _ResultBox:
    def __init__(self) -> None:
        self.value = ""

    def setPlainText(self, value: str) -> None:
        self.value = value


class _DummyWindow:
    def __init__(self, event: EventModel) -> None:
        self.event = event
        self.eval_expr_edit = _TextBox("$.details.payload.text.messages[-1].content")
        self.eval_result_box = _ResultBox()
        self.rebuild_called = False

    def _selected_event(self) -> EventModel:
        return self.event

    def _rebuild_timeline(self) -> None:
        self.rebuild_called = True
        raise AssertionError("ad-hoc eval must not rebuild the timeline")


def test_object_eval_does_not_rebuild_timeline_or_recurse() -> None:
    dummy = _DummyWindow(_llm_request_event())

    InteractiveTracerWindow._evaluate_current_expression(dummy)

    assert dummy.eval_result_box.value == "why is it erroring in the image"
    assert dummy.rebuild_called is False
