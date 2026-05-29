"""UI-independent core for BridgeTracer."""

from .schemas import (
    EventCategory,
    EventLevel,
    EventModel,
    FileRef,
    RecordingMetadata,
    RecordingState,
)
from .events import normalize_event, sort_events, validate_event_dict
from .recorder import Recorder, RecorderError
from .filters import PreRecordFilter, PostRecordFilter, apply_post_filter
from .triggers import StartTrigger, StopTrigger, TriggerEvaluator
from .storage import RecordingStorage
from .file_refs import FileRefRetriever, FileRefLimits
from .auth import build_auth_headers, redact_token

__all__ = [
    "EventCategory",
    "EventLevel",
    "EventModel",
    "FileRef",
    "RecordingMetadata",
    "RecordingState",
    "normalize_event",
    "sort_events",
    "validate_event_dict",
    "Recorder",
    "RecorderError",
    "PreRecordFilter",
    "PostRecordFilter",
    "apply_post_filter",
    "StartTrigger",
    "StopTrigger",
    "TriggerEvaluator",
    "RecordingStorage",
    "FileRefRetriever",
    "FileRefLimits",
    "build_auth_headers",
    "redact_token",
]
