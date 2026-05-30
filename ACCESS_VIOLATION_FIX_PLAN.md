# Access Violation Fix Plan

## Goal

Fix the Windows fatal access violation that occurs roughly 10 seconds after app startup/recording begins.

The crash stack points to Qt/PySide native object lifetime corruption while rebuilding the timeline:

```text
Current thread:
src/ui/timeline_view.py", line 25 in __init__
src/ui/timeline_view.py", line 291 in populate_events
src/ui/main_window.py", line 529 in _rebuild_timeline
src/ui/main_window.py", line 688 in _rebuild_from_controller
src/ui/main_window.py", line 671 in _poll_once
```

The SSE/httpx thread is alive during the crash, but the crashing thread is the UI thread creating timeline items.

## Primary Suspected Cause

`TimelineView.populate_events()` appears to tear down and rebuild a live `QGraphicsScene` while Qt still has pending paint/layout/signal work referencing old `QGraphicsItem` / `QGraphicsObject` instances.

Likely dangerous pattern:

```python
for conn in list(self.connectors):
    self._scene.removeItem(conn)
self.connectors.clear()

for item in list(self.items_map.values()):
    self._scene.removeItem(item)
self.items_map.clear()

self._scene.clear()
```

Then the code immediately creates new `EventCardItem` instances.

This can leave stale Python wrappers around deleted C++ Qt objects, especially if connectors keep references to card items.

## Secondary Suspected Cause

`ConnectorItem` stores raw references to graphics items:

```python
self.start_item = start_item
self.end_item = end_item
```

Then later dereferences them during paint/layout:

```python
p1 = self.start_item.pos()
p2 = self.end_item.pos()
```

If the scene is cleared while a repaint is pending, those references can point to deleted C++ Qt objects.

## Third Suspected Cause

The SSE worker may close an `httpx` stream from the GUI/main thread while the worker thread is blocked inside:

```python
for chunk in self._response.iter_text():
```

Closing native/socket resources from another thread can cause hard-to-reproduce crashes.

---

# Implementation Plan

## Phase 1 — Make Timeline Rebuild Safe

### 1.1 Replace partial item removal with a full scene swap

In `src/ui/timeline_view.py`, update `populate_events()` so it creates a fresh scene instead of manually removing items and then clearing the old scene.

Target shape:

```python
def populate_events(self, events: list[EventModel], visual_state: str = "main_desktop_timeline") -> None:
    self.setUpdatesEnabled(False)
    try:
        old_scene = self._scene

        self._scene = TimelineScene(self)
        self.setScene(self._scene)

        if old_scene is not None:
            old_scene.deleteLater()

        self.items_map = {}
        self.connectors = []

        if not events:
            return

        # existing layout/card/connector creation logic continues here

    finally:
        self.setUpdatesEnabled(True)
        self.viewport().update()
```

### 1.2 Remove the unsafe cleanup block

Delete any block shaped like:

```python
for conn in list(self.connectors):
    self._scene.removeItem(conn)

for item in list(self.items_map.values()):
    self._scene.removeItem(item)

self._scene.clear()
```

Do not mix manual `removeItem()` with `scene.clear()` during high-frequency rebuilds.

### 1.3 Disable updates while rebuilding

Ensure every full timeline rebuild is wrapped with:

```python
self.setUpdatesEnabled(False)
...
self.setUpdatesEnabled(True)
self.viewport().update()
```

This reduces paint calls while the scene is half-built.

---

# Phase 2 — Remove Fragile Signal Connections

## 2.1 Replace direct signal-to-signal connections

Avoid:

```python
item.clicked.connect(self.event_selected.emit)
```

Use a stable slot method:

```python
item.clicked.connect(self._on_card_clicked)
```

Add:

```python
def _on_card_clicked(self, event_id: str) -> None:
    self.event_selected.emit(event_id)
```

This makes object lifetime easier to reason about and avoids signal forwarding through objects that are constantly destroyed/recreated.

---

# Phase 3 — Make Connector Items Safer

## 3.1 Prefer coordinates over item references

Instead of storing references to `start_item` and `end_item`, compute connector start/end positions when building the scene and store immutable coordinates.

Current risky model:

```python
ConnectorItem(start_item, end_item)
```

Safer model:

```python
ConnectorItem(start_pos, end_pos)
```

Example:

```python
start_pos = start_item.sceneBoundingRect().center()
end_pos = end_item.sceneBoundingRect().center()
conn = ConnectorItem(start_pos, end_pos)
```

Then inside `ConnectorItem`:

```python
self.start_pos = QPointF(start_pos)
self.end_pos = QPointF(end_pos)
```

Painting should use only those stored points.

## 3.2 If dynamic connectors are required

If connectors must follow moving cards, use weak references plus validity checks.

But for a static rebuilt timeline, stored coordinates are simpler and safer.

---

# Phase 4 — Make SSE Worker Shutdown Safer

## 4.1 Do not close the SSE/httpx stream from the GUI thread

Avoid this in the main/UI thread:

```python
self._source.close()
```

while the worker may be inside:

```python
response.iter_text()
```

## 4.2 Use a short read timeout

Create the SSE event source with a short timeout so the worker can notice stop requests naturally.

Example:

```python
self._source = SSEEventSource(
    self.base_url,
    self.token,
    http_client=self.http_client,
    timeout=1.0,
)
```

## 4.3 Let the worker own the stream lifetime

In `stop()`:

```python
def stop(self) -> None:
    with self._lock:
        self._running = False

    self.requestInterruption()
    self.quit()
    self.wait(3000)
```

Let the worker thread close its own stream in its own `finally` block.

---

# Phase 5 — Reduce Timeline Rebuild Frequency

## 5.1 Avoid full rebuild on every poll when possible

Current flow appears to do:

```python
if total_new > 0:
    self._rebuild_from_controller()
```

This can cause repeated full scene destruction/recreation during streaming.

Short-term fix:

- Keep full rebuild, but debounce it.

Example:

```python
self._timeline_rebuild_pending = True
self._timeline_rebuild_timer.start(100)
```

Then rebuild at most every 100–250 ms.

## 5.2 Long-term fix

Incrementally append new timeline events instead of rebuilding the whole scene.

This is lower priority than fixing the crash.

---

# Phase 6 — Add Crash Reproduction Test

## 6.1 Add a timeline rebuild stress test

Create a small test or debug command that repeatedly calls `populate_events()` with growing event lists.

Target:

- 500 rebuilds.
- Mixed event types.
- Connectors enabled.
- No recording/SSE required.

Pseudo-test:

```python
def test_timeline_rebuild_stress(qtbot):
    view = TimelineView()
    qtbot.addWidget(view)

    for i in range(500):
        events = make_fake_events(i % 100)
        view.populate_events(events)
        QApplication.processEvents()
```

Expected result:

- No crash.
- No access violation.
- No deleted QObject wrapper errors.

## 6.2 Add start/stop stream stress test

Repeatedly start and stop recording/SSE.

Target:

- 50 cycles.
- No access violation.
- Worker thread exits cleanly.
- No leaked running threads.

---

# Phase 7 — Add Diagnostic Logging

Add temporary debug logs around timeline rebuilds:

```python
logger.debug("timeline rebuild start: events=%s", len(events))
logger.debug("old scene=%s items=%s", id(old_scene), len(old_scene.items()) if old_scene else 0)
logger.debug("new scene=%s", id(self._scene))
logger.debug("timeline rebuild end")
```

Add worker shutdown logs:

```python
logger.debug("SSE worker stop requested")
logger.debug("SSE worker exiting")
logger.debug("SSE source closed inside worker")
```

Remove or lower to trace/debug once stable.

---

# Phase 8 — Validation Checklist

Run:

```powershell
python -m src.app.main
```

Then verify:

- App starts cleanly.
- Recording can run for at least 60 seconds.
- No access violation.
- Timeline keeps updating.
- Start/stop recording works repeatedly.
- Closing the app exits without hanging.
- No `RuntimeError: Internal C++ object already deleted`.
- No worker thread left running after close.

---

# Recommended Patch Order

1. Scene swap in `TimelineView.populate_events()`.
2. Remove manual `removeItem()` cleanup.
3. Disable updates during rebuild.
4. Replace signal-to-signal connection with `_on_card_clicked()`.
5. Convert connectors to stored coordinates.
6. Make SSE stream shutdown worker-owned.
7. Add rebuild debounce.
8. Add stress tests.

---

# Expected Result

The access violation should stop once Qt no longer paints or signals through stale `QGraphicsItem` wrappers during timeline rebuilds.

The most important fix is:

> Rebuild the timeline using a fresh `QGraphicsScene`, and let the old scene die via `deleteLater()` instead of manually removing/clearing live items.
