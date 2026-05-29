"""Opt-in live e2e against a REAL running AI-Bridge.

Skipped by default. To run against a live bridge:

    set AI_BRIDGE_ADMIN_TOKEN=<token>
    set BRIDGE_TRACER_LIVE=1
    # optional: set BRIDGE_TRACER_URL=http://127.0.0.1:8765
    pytest tests/test_live_bridge_e2e.py -v

The token is read from the environment only — never hardcoded/committed.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

LIVE = os.environ.get("BRIDGE_TRACER_LIVE") == "1"
TOKEN = os.environ.get("AI_BRIDGE_ADMIN_TOKEN", "")
URL = os.environ.get("BRIDGE_TRACER_URL", "http://127.0.0.1:8765")

pytestmark = pytest.mark.skipif(
    not (LIVE and TOKEN),
    reason="live bridge e2e: set BRIDGE_TRACER_LIVE=1 and AI_BRIDGE_ADMIN_TOKEN to run",
)


def _bridge_reachable() -> bool:
    try:
        import httpx
        return httpx.get(f"{URL}/health", timeout=3).status_code == 200
    except Exception:
        return False


def test_records_from_the_real_running_bridge():
    if not _bridge_reachable():
        pytest.skip(f"bridge not reachable at {URL}")

    from PySide6.QtWidgets import QApplication
    from src.core.schemas import RecordingState
    from src.ui.controller import BridgeTracerController
    from src.ui.interactive_window import InteractiveTracerWindow

    QApplication.instance() or QApplication([])

    controller = BridgeTracerController()
    controller.connect(URL, TOKEN)
    window = InteractiveTracerWindow(events=[], controller=controller)

    window.start_btn.click()  # real click -> live poll of /logs or SSE stream
    assert controller.status.recording_state == RecordingState.RECORDING
    
    # Wait/process events if streaming/async
    import time
    start = time.time()
    while window.event_count() == 0 and time.time() - start < 3.0:
        QApplication.processEvents()
        time.sleep(0.05)

    recorded = window.event_count()
    assert recorded > 0, "expected to record existing bridge events"

    # Selecting the latest event populates the inspector.
    window.select_event(controller.events[-1].id)
    assert window.inspector_text().strip() != ""

    window.stop_btn.click()
    assert controller.status.recording_state == RecordingState.STOPPED
    assert not window._poll_timer.isActive()
    window.close()
