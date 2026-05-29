from __future__ import annotations

from datetime import datetime, timezone

from src.core.schemas import EventCategory, EventLevel, EventModel, FileRef


def build_sample_events() -> list[EventModel]:
    """Deterministic trace used by the UI mock states and screenshot script."""
    ts = datetime(2026, 5, 28, 18, 42, 11, 482000, tzinfo=timezone.utc)
    common = {
        "run_id": "run_8f31b2",
        "session_id": "sess_dev_004",
        "request_id": "req_9ae1",
        "timestamp": ts,
    }
    return [
        EventModel(
            id="evt_http_request",
            type="http.request",
            category=EventCategory.HTTP,
            level=EventLevel.INFO,
            summary="POST /api/send",
            details={"method": "POST", "path": "/api/send", "status": 200, "duration": "231ms"},
            duration_ms=231,
            **common,
        ),
        EventModel(
            id="evt_http_response",
            type="http.response",
            category=EventCategory.HTTP,
            level=EventLevel.SUCCESS,
            summary="200 OK",
            details={"status": 200, "duration": "231ms"},
            duration_ms=231,
            parent_event_id="evt_http_request",
            **common,
        ),
        EventModel(
            id="evt_llm_request",
            type="llm.request",
            category=EventCategory.LLM,
            level=EventLevel.INFO,
            summary="LLM request sent",
            details={"messages": 12, "tokens": 4201, "model": "local-llm"},
            parent_event_id="evt_http_request",
            **common,
        ),
        EventModel(
            id="evt_llm_response",
            type="llm.response",
            category=EventCategory.LLM,
            level=EventLevel.INFO,
            summary="LLM response received",
            details={
                "duration": "1.84s",
                "model": "local-llm",
                "tokens": "prompt 4201 - completion 908",
                "finish_reason": "tool_calls",
                "raw_response": {
                    "role": "assistant",
                    "content": "<tool_call>...",
                    "tool_calls": [{"name": "read_file"}],
                },
            },
            duration_ms=1840,
            parent_event_id="evt_llm_request",
            **common,
        ),
        EventModel(
            id="evt_tool_call",
            type="tool.call",
            category=EventCategory.TOOL,
            level=EventLevel.INFO,
            summary="read_file",
            details={"tool": "read_file", "path": "config.py", "state": "queued"},
            parent_event_id="evt_llm_response",
            **common,
        ),
        EventModel(
            id="evt_tool_result",
            type="tool.result",
            category=EventCategory.TOOL,
            level=EventLevel.SUCCESS,
            summary="tool result",
            details={"status": "success", "chars": 18204},
            duration_ms=64,
            parent_event_id="evt_tool_call",
            **common,
        ),
        EventModel(
            id="evt_file_ref",
            type="file.ref.created",
            category=EventCategory.FILE,
            level=EventLevel.SUCCESS,
            summary="file ref",
            details={"name": "screenshot.png", "mime": "image/png"},
            refs=[FileRef(ref_id="file_trace", path="trace.json", mime="application/json", size_bytes=412000)],
            parent_event_id="evt_tool_result",
            **common,
        ),
        EventModel(
            id="evt_parser_warning",
            type="parser.warning",
            category=EventCategory.PARSER,
            level=EventLevel.WARNING,
            summary="Warning: max_tokens reached",
            details={"recovery": "retry"},
            parent_event_id="evt_llm_response",
            **common,
        ),
        EventModel(
            id="evt_parse_error",
            type="parser.error",
            category=EventCategory.ERROR,
            level=EventLevel.ERROR,
            summary="JSON parse failed",
            details={"line": 1, "column": 9, "recovery": "retry"},
            parent_event_id="evt_parser_warning",
            **common,
        ),
        EventModel(
            id="evt_latency",
            type="performance.latency",
            category=EventCategory.PERFORMANCE,
            level=EventLevel.WARNING,
            summary="Latency spike",
            details={"duration": "LLM wait 1.84s"},
            duration_ms=1840,
            parent_event_id="evt_llm_request",
            **common,
        ),
    ]

