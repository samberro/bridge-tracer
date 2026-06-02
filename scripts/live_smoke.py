"""LIVE end-to-end smoke test against a running bridge (127.0.0.1:8765) and
chat app (127.0.0.1:8080). Drives the real MainWindow: connect -> start ->
ingest live SSE events -> screenshot real data -> stop. Offscreen so it is
fully automated, but the network/bridge is real. Requires AI_BRIDGE_ADMIN_TOKEN.

Run: QT_QPA_PLATFORM=offscreen python scripts/live_smoke.py
"""
from __future__ import annotations

import os
import sys
import threading
import time
import urllib.request
import json
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtCore import QElapsedTimer  # noqa: E402

from src.ui.main_window import MainWindow  # noqa: E402
from src.core.schemas import RecordingState  # noqa: E402

BRIDGE = "http://127.0.0.1:8765"
TOKEN = os.environ.get("AI_BRIDGE_ADMIN_TOKEN", "").strip()


def pump(app, seconds: float):
    t = QElapsedTimer()
    t.start()
    while t.elapsed() < seconds * 1000:
        app.processEvents()
        time.sleep(0.02)


def gen_traffic():
    """Best-effort: POST to the bridge /chat to create NEW trace events.
    Non-fatal if the LLM backend is slow/down (errors still produce events)."""
    try:
        body = json.dumps({"session_id": "tracer-live-e2e",
                            "user_request": "say hi"}).encode()
        req = urllib.request.Request(
            f"{BRIDGE}/chat", data=body, method="POST",
            headers={"Authorization": f"Bearer {TOKEN}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as r:
            print(f"[traffic] /chat -> HTTP {r.status}")
    except Exception as exc:
        print(f"[traffic] /chat raised (non-fatal): {type(exc).__name__}: {str(exc)[:120]}")


app = QApplication.instance() or QApplication(sys.argv[:1])

print(f"TOKEN present: {bool(TOKEN)} (len {len(TOKEN)})")
w = MainWindow(events=[], visual_state="main_desktop_timeline")
w.resize(1600, 950)
w.show()
app.processEvents()

# 1) Connect to the real bridge.
w.url_edit.setText(BRIDGE)
w.token_edit.setText(TOKEN)
w._on_connect()
app.processEvents()
print("connected:", w.controller.status.connected,
      "| trace_available:", w.controller.trace_available(),
      "| label:", w.controller.status.label)
assert w.controller.status.connected, "did not connect to live bridge"
assert TOKEN not in w.status_label.text(), "token leaked into status label!"

# 2) Start recording (opens the live SSE worker -> snapshot + live trace events).
w._on_start()
print("recording state:", w.controller.status.recording_state)
assert w.controller.status.recording_state == RecordingState.RECORDING

# 3) Generate live traffic in the background, then pump the Qt loop so queued
#    SSE signals are delivered on the GUI thread.
threading.Thread(target=gen_traffic, daemon=True).start()
pump(app, 8.0)

count = w.event_count()
print(f"events ingested from LIVE bridge: {count}")
shot = ROOT / "docs" / "diagnostic-shots" / "live_recording.png"
w.grab().save(str(shot))
print("screenshot:", shot.name)

# Select the last event to exercise the inspector against real data.
if count:
    last_id = w.model.events[-1].id
    w.select_event(last_id)
    app.processEvents()
    insp = w.inspector_text()
    print("inspector populated:", bool(insp.strip()),
          "| has type field:", '"type"' in insp)

# 4) Stop and verify clean shutdown.
w._on_stop()
app.processEvents()
print("after stop -> state:", w.controller.status.recording_state,
      "| streaming:", w.controller.is_streaming)
assert w.controller.status.recording_state == RecordingState.STOPPED

w.close()
w.deleteLater()
app.processEvents()

# 5) Report leaked threads (SSE worker hygiene — relevant to A5).
alive = [t.name for t in threading.enumerate() if "SSE" in t.name or "BridgeTracer" in t.name]
print("leaked tracer threads after close:", alive or "none")
print(f"\nLIVE E2E RESULT: connected + recorded {count} real events, stop clean.")
