"""Post-recording file-reference retrieval (BridgeTracer.md §9).

Honors the configured limits exactly:

    max_file_bytes_per_ref = 5 MB
    max_total_file_bytes  = 50 MB
    max_inline_text_chars = 100,000

Retrieval failures must produce a `file.ref.retrieve_failed` event so the
timeline shows the user what didn't come back.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .schemas import EventCategory, EventLevel, EventModel, FileRef


@dataclass(frozen=True)
class FileRefLimits:
    max_file_bytes_per_ref: int = 5 * 1024 * 1024
    max_total_file_bytes: int = 50 * 1024 * 1024
    max_inline_text_chars: int = 100_000


@dataclass
class FileRefRetrievalResult:
    refs: list[FileRef]
    events: list[EventModel]
    total_bytes: int


# A fetcher returns (mime, size_bytes, data). `data` is bytes for binary and
# str for text. Implementations live in bridge_client; we accept any callable
# so tests can pass a dict-driven stub.
FetcherFn = Callable[[FileRef], tuple[Optional[str], int, Optional[bytes | str]]]


class FileRefRetriever:
    def __init__(self, fetcher: FetcherFn, limits: Optional[FileRefLimits] = None) -> None:
        self._fetch = fetcher
        self._limits = limits or FileRefLimits()

    @property
    def limits(self) -> FileRefLimits:
        return self._limits

    def retrieve(self, refs: Iterable[FileRef]) -> FileRefRetrievalResult:
        out_refs: list[FileRef] = []
        events: list[EventModel] = []
        total = 0
        for ref in refs:
            try:
                mime, size, data = self._fetch(ref)
            except Exception as exc:
                events.append(self._failed_event(ref, str(exc)))
                out_refs.append(ref.model_copy(update={
                    "retrieved": False, "error": str(exc),
                }))
                continue

            if size > self._limits.max_file_bytes_per_ref:
                events.append(self._failed_event(
                    ref, f"size {size} exceeds per-ref limit {self._limits.max_file_bytes_per_ref}"
                ))
                out_refs.append(ref.model_copy(update={
                    "retrieved": False, "size_bytes": size, "mime": mime,
                    "error": "per_ref_limit_exceeded",
                }))
                continue

            if total + size > self._limits.max_total_file_bytes:
                events.append(self._failed_event(
                    ref, f"would exceed total cap {self._limits.max_total_file_bytes}"
                ))
                out_refs.append(ref.model_copy(update={
                    "retrieved": False, "size_bytes": size, "mime": mime,
                    "error": "total_limit_exceeded",
                }))
                continue

            preview, truncated = self._inline_preview(data, mime)
            out_refs.append(ref.model_copy(update={
                "retrieved": True,
                "size_bytes": size,
                "mime": mime,
                "content_preview": preview,
                "truncated": truncated,
            }))
            total += size

        return FileRefRetrievalResult(refs=out_refs, events=events, total_bytes=total)

    def _inline_preview(self, data, mime: Optional[str]) -> tuple[Optional[str], bool]:
        """Return (preview, truncated). Binary content yields None preview."""
        if data is None:
            return None, False
        is_text = isinstance(data, str) or (mime and str(mime).startswith("text/"))
        if not is_text:
            return None, False
        text = data if isinstance(data, str) else data.decode("utf-8", errors="replace")
        cap = self._limits.max_inline_text_chars
        if len(text) > cap:
            return text[:cap], True
        return text, False

    def _failed_event(self, ref: FileRef, reason: str) -> EventModel:
        return EventModel(
            type="file.ref.retrieve_failed",
            category=EventCategory.FILE,
            level=EventLevel.ERROR,
            summary=f"Failed to retrieve {ref.path}: {reason}",
            details={"ref_id": ref.ref_id, "path": ref.path, "reason": reason},
        )
