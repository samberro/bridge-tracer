# Bridge Tracer — Phase 0 Live Diagnostic Baseline

Date: 2026-06-02 · Env: Windows 11, Python 3.12.10, PySide6 6.11.1
Method: offscreen render (`QT_QPA_PLATFORM=offscreen`) of the real `MainWindow`
for each visual state, plus a rebuild-timing/crash stress probe. Screenshots in
`docs/diagnostic-shots/`.

## Confirmed root causes

### 1. Global stylesheet is dropped by Qt (highest-leverage UX bug) — CONFIRMED
`_STYLE` (`src/ui/main_window.py:62`) is applied **raw** at `:163` and `:269`,
never `.format()`-ed. Static probe output:
```
contains '{{' (format placeholder left raw): True
contains '{BACKGROUND}' token: True
first 120 chars: '\nQMainWindow, QWidget {{ background: {BACKGROUND}; ...'
```
Qt's QSS parser rejects the doubled braces / unresolved tokens, so the **entire
global theme is ignored**. In the screenshots the toolbar, inspector panel, tab
bar, tree, and scrollbars render in **default light-gray**, clashing with the
dark `QGraphicsScene` canvas (which sets its background brush in code, not via
QSS). This is the "cluttered/unstyled" perception. Splitter handles are also
left at the default thin `handleWidth=4` and unstyled → invisible and hard to
grab, which is why "drag-to-resize doesn't work" even though the splitter tree
is structurally correct.

### 2. Full-scene rebuild cost (sluggishness) — CONFIRMED
`TimelineView.populate_events()` rebuilds the whole scene every call. Measured:

| events | ms / full rebuild |
|-------:|------------------:|
| 10     | ~6 |
| 100    | ~6 |
| 300    | ~17 |
| 600    | ~35 |
| 1000   | ~59 |

During live recording the rebuild fires every 125ms (debounce) **plus** the
tree clear/repopulate, inspector teardown, and recursive object-tree walk on top
— so at a few hundred+ events the GUI thread spends most of each second
rebuilding. Validates the **incremental-append** strategy (Workstream B).

### 3. Access violation — NOT reproduced headless
400 high-frequency rebuilds with interleaved `processEvents()` survived in
offscreen mode (exit 0). The crash is a live-paint timing race on a real display;
current partial mitigations (fresh-scene swap + `deleteLater`, coordinate-based
connectors, SSE `timeout=1.0`) reduce but don't prove it gone. A5 (recorder lock,
worker-owned SSE shutdown) and B5 (permanent stress test) remain warranted; B5
should also run on a non-offscreen display.

### 4. Sizing — CONFIRMED from live widget state
`sidebar=(min 220, max 420)`, `inspector=(min 300, max 900)`, `logs_h=42` (fixed).
Inspector is visibly cramped; logs strip unreadable.

## NEW finding (not in original plan): test suite + capture harness have drifted
`python -m pytest -q` → **19 failed, 152 passed, 1 skipped**. Triaged:

- **Drift / stale tests (majority):** tests expect an older `SSEStreamWorker`
  QThread-style API (`.isFinished()`), an older `FakeSSEWorker(__init__)` without
  the `at` kwarg, and a removed `use_mockup_backdrop` param on the window. e.g.
  `test_ui_streaming`, `test_recording_transport`, `test_ui_app_window`.
- **Broken tooling:** `scripts/capture_bridge_tracer.py` passes
  `use_mockup_backdrop=True` to `BridgeTracerWindow` → `TypeError`. The documented
  screenshot/visual-QA harness does **not run**. (I worked around it with a
  throwaway renderer for this diagnostic.)
- **Possibly real (verify):** `test_ui_live_polling::test_stop_halts_polling`
  (`assert 0 == 1`), `test_ui_controller::...without_exposing_bearer_token`
  (security), `test_timeline_layout::...does_not_force_scroll_on_rebuild`
  (`set_selected_event` calls `ensureVisible` → forced scroll on every rebuild).

**Action:** add a task to repair the capture harness and triage/update the drifted
tests so the suite is green before/with the perf+UX work (otherwise F1–F3 build on
a red baseline). See plan addendum below.

## Screenshots
- `docs/diagnostic-shots/main_desktop_timeline.png` — light shell vs dark canvas; cramped inspector.
- `docs/diagnostic-shots/event_detail_inspector.png`
- `docs/diagnostic-shots/filter_recording_sidebar.png`
- `docs/diagnostic-shots/timeline_filmstrip_focused.png`

(Note: text renders as missing-glyph boxes in offscreen headless mode — a font
artifact of the capture environment, not a product bug. Re-verify typography on a
real display during the responsiveness pass.)

## Live server E2E (bridge :8765 + chat :8080) — executed, PASSED with caveats
Drove the real `MainWindow` against the **live bridge** (real SSE), token from
`AI_BRIDGE_ADMIN_TOKEN`. Endpoints confirmed: `/trace/events` (200, EventModel
shape), `/trace/events/stream` (SSE `event: snapshot` then `trace`), `/logs`
(`{"events":[...]}`), `/config` (200). All 401 without bearer.

Result (`scripts/live_smoke.py`, offscreen):
```
connected: True | trace_available: True | label: "...ws connected"
recording state: RECORDING ; /chat -> HTTP 200 (LLM backend up)
events ingested from LIVE bridge: 264
inspector populated: True | has "type" field: True
after stop -> STOPPED | streaming: False | leaked tracer threads: none
```
**Data path works end-to-end**: connect → SSE snapshot+live → recorder → model →
timeline → inspector → clean stop, no token leak, no leaked threads.

### NEW live-only finding — timeline is unreadable at real volume (HIGH)
Screenshot `docs/diagnostic-shots/live_recording.png` (264 real events) shows
**cards overlapping/stacked on top of each other** in a couple of time clusters
with most of the canvas empty. `TimelineView._layout_events` positions cards by
absolute timestamp (`px_per_second` from the full time span) with only a
per-lane min-spacing fallback, so bursts collapse into overlapping stacks while
idle gaps waste space. Sample data (8 events) never exposed this. **Add to
Workstream B**: density handling — lane packing / collision avoidance, a
"fit/zoom-to-events" default, and/or log-or-index-based x instead of raw wall-clock.

## Recording + filtering live test (REAL InteractiveTracerWindow) — CRITICAL bugs found
Re-ran against the live bridge using the actual app window (not raw MainWindow).
Two recording-path bugs, both proven:
- **SSE worker dies on 1s read timeout, no reconnect** (`controller.py:79 timeout=1.0`):
  `[SSE ERROR] timed out` at t≈1s, `is_streaming`→False, thread exits. A message
  sent mid-recording (HTTP 200) never appeared.
- **No UI-refresh path when polling is off**: with a patched 25s read timeout the
  worker survived and `controller.events` reached **304**, but the UI
  `event_count()` stayed **0** — the window only syncs recorder→model via the
  poll timer, which `InteractiveTracerWindow` disables in SSE mode. So live events
  are recorded but never shown.
- **Confirmed per user directive:** **0 `/logs` (poll) calls** with polling off.
- **Filtering works** (sample set of 10): LLM-only→2, search 'tool'→3,
  errors-only→1, clear→10.
- Fix plan: Workstream **H** (H1 survive-idle+reconnect, H2 event-driven refresh
  / remove poll-as-refresh, H3 regression test).

## Progress
- **D1 landed (stylesheet fix):** `_STYLE` is now `.format()`-resolved and the four
  malformed QSS blocks repaired; splitter handles set to 6px with hover color.
  Re-render `docs/diagnostic-shots/after_d1_main_desktop.png` shows the full dark
  theme applied across toolbar/inspector/tabs/tree/scrollbars (was light-gray).
- **Extra flakiness signal for A5/G2:** the full suite shows a *non-deterministic*
  streaming failure (`test_ui_streaming::test_controller_wires_sse_worker` fails in
  the full run but passes in isolation) → SSE worker threads leak across tests.
  Reinforces the recorder-lock + worker-owned-shutdown work in A5.
