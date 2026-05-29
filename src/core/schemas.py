"""Pydantic event schema for BridgeTracer.

Single source of truth for event shape, category, severity, and recording
lifecycle. UI code consumes these models but never mutates them in place.

Mirrors BridgeTracer.md §1 ("Event Recording") and §2 ("Recording Session
Control") exactly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventCategory(str, Enum):
    SYSTEM = "system"
    CONFIG = "config"
    HTTP = "http"
    AUTH = "auth"
    SESSION = "session"
    LLM = "llm"
    TOOL = "tool"
    MCP = "mcp"
    FILE = "file"
    PARSER = "parser"
    ERROR = "error"
    PERFORMANCE = "performance"


class EventLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class RecordingState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class FileRef(BaseModel):
    """A reference to a file produced/observed during a trace event.

    `retrieve_file_ref` later hydrates `content_preview` / `mime`, but the
    base reference itself is the testable bit that flows through events.
    """
    model_config = ConfigDict(extra="forbid")

    ref_id: str
    path: str
    mime: Optional[str] = None
    size_bytes: Optional[int] = Field(default=None, ge=0)
    retrieved: bool = False
    truncated: bool = False
    content_preview: Optional[str] = None
    error: Optional[str] = None


class EventModel(BaseModel):
    """Normalized bridge-trace event.

    `id` and `timestamp` are auto-populated when the source dict omits them,
    which is what the plan calls "normalization". `parent_event_id` lets us
    group LLM-request → tool-call → tool-result chains in the timeline view.
    """
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}")
    run_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: str
    category: EventCategory
    level: EventLevel = EventLevel.INFO
    summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    refs: list[FileRef] = Field(default_factory=list)
    duration_ms: Optional[float] = Field(default=None, ge=0)
    parent_event_id: Optional[str] = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def _coerce_timestamp(cls, value: Any) -> Any:
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, str):
            # Accept "Z" suffix; pydantic does the rest.
            return value.replace("Z", "+00:00") if value.endswith("Z") else value
        return value


class RecordingMetadata(BaseModel):
    """Per-recording cumulative metadata. Persisted with the events."""
    model_config = ConfigDict(extra="forbid")

    recording_id: str = Field(default_factory=lambda: f"rec_{uuid4().hex}")
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    duration_ms: Optional[float] = Field(default=None, ge=0)
    event_count: int = Field(default=0, ge=0)
    active_filters: dict[str, Any] = Field(default_factory=dict)
    active_triggers: dict[str, Any] = Field(default_factory=dict)
    state: RecordingState = RecordingState.IDLE
    notes: str = ""
