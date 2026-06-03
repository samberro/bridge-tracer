from __future__ import annotations

import threading

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from src.ui.async_runner import AsyncRunner


def _wait_until(predicate, *, timeout_ms: int = 1500) -> None:
    deadline = QTimer()
    deadline.setSingleShot(True)
    loop = QEventLoop()
    deadline.timeout.connect(loop.quit)
    deadline.start(timeout_ms)
    while not predicate() and deadline.isActive():
        QCoreApplication.processEvents(QEventLoop.AllEvents, 20)
    if deadline.isActive():
        deadline.stop()
    else:
        loop.quit()


def test_async_runner_executes_callable_off_caller_thread(qapp_session) -> None:
    runner = AsyncRunner()
    caller_thread = threading.get_ident()
    results: list[tuple[int, str]] = []

    runner.finished.connect(lambda call_id, value: results.append((value[0], call_id)))
    token = runner.run(lambda: (threading.get_ident(), "ok"))

    _wait_until(lambda: bool(results))

    assert results[0][1] == token
    assert results[0][0] != caller_thread


def test_async_runner_emits_failures(qapp_session) -> None:
    runner = AsyncRunner()
    failures: list[tuple[str, BaseException]] = []

    def explode() -> None:
        raise RuntimeError("slow bridge failed")

    runner.failed.connect(lambda call_id, exc: failures.append((call_id, exc)))
    token = runner.run(explode)

    _wait_until(lambda: bool(failures))

    assert failures[0][0] == token
    assert isinstance(failures[0][1], RuntimeError)
    assert str(failures[0][1]) == "slow bridge failed"


def test_async_runner_rejects_duplicate_in_flight_key(qapp_session) -> None:
    runner = AsyncRunner()
    gate = threading.Event()

    runner.run(lambda: gate.wait(0.2), key="connect")
    with pytest.raises(RuntimeError, match="already in flight"):
        runner.run(lambda: None, key="connect")
    gate.set()
    _wait_until(lambda: not runner.is_in_flight("connect"))
