from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class _AsyncCallSignals(QObject):
    finished = Signal(str, object)
    failed = Signal(str, object)


class _AsyncCall(QRunnable):
    def __init__(self, call_id: str, fn: Callable[[], object], signals: _AsyncCallSignals) -> None:
        super().__init__()
        self.call_id = call_id
        self.fn = fn
        self.signals = signals

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn()
        except BaseException as exc:
            self.signals.failed.emit(self.call_id, exc)
        else:
            self.signals.finished.emit(self.call_id, result)


class AsyncRunner(QObject):
    """Run blocking callables off the Qt GUI thread.

    `key` is optional but useful for UI operations like connect or poll where
    concurrent duplicate work would race the visible state.
    """

    finished = Signal(str, object)
    failed = Signal(str, object)

    def __init__(self, *, pool: QThreadPool | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = pool or QThreadPool.globalInstance()
        self._signals = _AsyncCallSignals(self)
        self._signals.finished.connect(self._on_finished)
        self._signals.failed.connect(self._on_failed)
        self._in_flight_by_key: dict[str, str] = {}
        self._key_by_call_id: dict[str, str] = {}

    def run(self, fn: Callable[[], object], *, key: str | None = None) -> str:
        if key is not None and key in self._in_flight_by_key:
            raise RuntimeError(f"async call already in flight: {key}")

        call_id = key or uuid4().hex
        if key is not None:
            self._in_flight_by_key[key] = call_id
            self._key_by_call_id[call_id] = key

        self._pool.start(_AsyncCall(call_id, fn, self._signals))
        return call_id

    def is_in_flight(self, key: str) -> bool:
        return key in self._in_flight_by_key

    @Slot(str, object)
    def _on_finished(self, call_id: str, value: object) -> None:
        self._clear_key(call_id)
        self.finished.emit(call_id, value)

    @Slot(str, object)
    def _on_failed(self, call_id: str, exc: object) -> None:
        self._clear_key(call_id)
        self.failed.emit(call_id, exc)

    def _clear_key(self, call_id: str) -> None:
        key = self._key_by_call_id.pop(call_id, None)
        if key is not None and self._in_flight_by_key.get(key) == call_id:
            del self._in_flight_by_key[key]
