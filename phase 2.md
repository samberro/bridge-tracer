# BridgeTracer: real timeline main window + true (trace-based) recording

## Context

BridgeTracer currently "records" by polling the bridge's `/logs` endpoint, which
only carries **LLM request/response** entries — it piggybacks on the chat
logging system rather than a real trace feed. The interactive window is a flat
`QTreeWidget` list + text inspector; it has none of the approved mockup's main
window: the **timeline lanes**, **parent/child connectors**, the
**filters / recording / connection sidebar**, the raw-JSON panel, triggers, or
post-record filters. The rich layout exists only as a **non-interactive
QPainter mock** (`src/ui/app_window.py`, used for visual-QA capture).

Goal: (A) give the bridge a **dedicated trace event system** emitting the full
event taxonomy (separate from `/logs`), and (B) build the **real interactive
main window** (QGraphicsScene timeline + sidebar + inspector) consuming it, so
recording captures true bridge activity and looks/behaves like the mockups.

Decisions (confirmed): full taxonomy now · QGraphicsScene interactive timeline ·
keep `/logs` as a fallback.

Already done and reused: the tracer **core** (`src/core/`: `schemas.EventModel`
taxonomy, `recorder`, `filters.PreRecordFilter/PostRecordFilter`,
`triggers.StartTrigger/StopTrigger/TriggerEvaluator`, `storage` incl. JSONL,
`file_refs.FileRefRetriever`) and `bridge_client` (`client.list_events/list_runs/
list_sessions/fetch_file_ref` already target `/trace/*`; `stream.SSEEventSource`).
`view_models.TimelineViewModel.lanes()/selected_detail()/compare_event_details`.

---

## Workstream A — Ai_Bridge: dedicated trace bus + `/trace/*` API

Mirror the proven pub/sub in `Ai_Bridge/server_logs.py` (`_SUBSCRIBERS` queues,
`emit_llm_log`, `subscribe/unsubscribe`, ring buffer) but for normalized trace
events.

- **`Ai_Bridge/trace_bus.py`** (new): `emit_trace(**fields)` builds an
  EventModel-shaped dict (`id, run_id, session_id, request_id, timestamp(ISO),
  type, category, level, summary, details, refs, duration_ms, parent_event_id`),
  appends to a bounded ring buffer with a monotonic cursor, and fans out to
  subscribers. `list_trace_events(since=<cursor>)`, `subscribe_trace()`,
  `unsubscribe_trace()`, `reset_for_tests()`. Gated by
  `config.TRACE_ENABLED` (default on). Never store/echo bearer tokens (reuse the
  redaction discipline already in the tracer's `core/auth`).
- **Instrumentation (full taxonomy)** — call `emit_trace` at:
  - HTTP: `@app.middleware("http")` in `main.py` → `http.request` on entry,
    `http.response` on exit with `status_code` + `duration_ms` (redact `authorization`).
  - LLM: `llm_client.py` (alongside the existing `emit_llm_log` at lines ~78/103/140)
    → `llm.request` / `llm.response`.
  - Tool: `chat_engine.py` + `tool_call_store.py`
    (`create_tool_call_record`/`mark_tool_running`/`finish_tool_call`) →
    `tool.call_detected` / `tool.started` / `tool.finished` / `tool.failed`,
    `parent_event_id` = the originating `llm.response`.
  - File: `attachments.py create_attachment` → `file.ref_created`; ref fetch →
    `file.ref_retrieved` with `refs:[{ref_id,path,mime,size_bytes}]`.
  - Config: config patch/reload path → `config.loaded` / `config.changed`.
  - Auth: `require_admin` (`main.py:43`) → `auth.success` / `auth.failure`.
  - MCP: `mcp_servers.py` call sites → `mcp.call_started` / `mcp.call_finished`.
  - Parser/error: chat_engine tool-parse failures → `parser.warning` / `error.exception`.
- **Endpoints in `main.py`** (admin-authed, mirror `/logs` + `/logs/events`):
  `GET /trace/events?since=<cursor>` (pull), `GET /trace/events/stream` (SSE),
  `GET /trace/runs`, `GET /trace/sessions`, `GET /trace/file_refs/{ref_id}`
  (proxy to existing attachment fetch). These are exactly what the tracer's
  `BridgeClient` already calls.
- **TDD**: `tests/test_trace_bus.py` (emit/list/since-cursor/subscribe/redaction),
  endpoint tests via FastAPI `TestClient` (auth, SSE snapshot+stream framing),
  and per-instrumentation unit tests (tool lifecycle emits 3 events with parent
  linkage, etc.).

## Workstream B — Bridge_Tracer: ingest `/trace/*` (SSE primary, pull + `/logs` fallback)

- `bridge_client/client.py`: `list_events()` already hits `/trace/events`; add
  `since` cursor passthrough (present) and a `trace_available()` probe.
- `ui/controller.py`: add `start_stream()` using `bridge_client/stream.SSEEventSource`
  on a **`QThread` worker** that emits a Qt signal per event (marshal to UI
  thread); `recorder.feed` on the UI thread. `pull_trace(since)` for pull mode.
  Source selection: try `/trace/events` → on 404 fall back to the existing
  `pull_logs` (`/logs` + `map_log_event`). Trace events are already
  EventModel-shaped → feed via `normalize_event` (no mapping).
- Keep existing dedupe-by-id and record-only-while-RECORDING semantics.
- **TDD**: `tests/test_pull_trace.py` (dedup, since cursor, 404→/logs fallback),
  SSE worker test with a mock stream (reuse `MockTransport`), thread-marshalling
  smoke test.

## Workstream C — Bridge_Tracer: real interactive main window (QGraphicsScene)

- **`src/ui/timeline_view.py`** (new): `TimelineScene(QGraphicsScene)` +
  `TimelineView(QGraphicsView)`. Category lanes (rows) from
  `TimelineViewModel.lanes()`; time-ordered event cards as `QGraphicsItem`s
  color-coded via `theme.CATEGORY_COLORS`; cubic **connector lines** for
  `parent_event_id`; selection highlight; click emits `event_selected(id)`;
  zoom/pan. Mirrors the geometry the painted `app_window._draw_main_state`
  already encodes (reuse it as the visual spec).
- **`src/ui/main_window.py`** (new; supersedes `interactive_window.py` as the app
  window — keep the toolbar/connection/save-load/poll logic, move it in):
  - Top toolbar: Connect / Start / Stop / Save / Load + status (existing real
    widgets).
  - Left sidebar (`QDockWidget`/`QFrame`): **Connection** (URL/token/save-token/
    auth status), **Recording** (state/event count/elapsed), **Pre-record
    filters** (category toggles, session/run scope), **Triggers** (start/stop
    trigger config), **Post-record filters** (category toggles, text search,
    duration, errors-only).
  - Center: `TimelineView`.
  - Right: inspector (detail fields + badges + raw JSON + related events +
    **file-ref preview** + actions Copy JSON / Open File Ref / Compare / Pin).
  - Bottom: collapsible raw JSON/log panel.
- **Wire to existing core**: pre-record filters → `Recorder(prefilter=PreRecordFilter)`;
  triggers → `TriggerEvaluator` gating auto start/stop; post-record filters →
  `filters.apply_post_filter` over the displayed model (non-destructive);
  file-ref preview → `FileRefRetriever` via `/trace/file_refs`; compare →
  `view_models.compare_event_details`; JSONL export → `RecordingStorage.save_jsonl`.
- `src/app/main.py` → launch the new main window.
- Retire the flat `QTreeWidget` as primary (optionally keep as an alternate
  "list view" tab). The painted `app_window.py` stays only as the visual-QA
  reference until the real window matches the mockups.
- **TDD** (offscreen Qt, `QTest`): timeline builds N lane items for N events,
  clicking a card selects it + updates inspector, connectors drawn for
  parent/child, post-filter hides categories, trigger auto-starts on matching
  event, file-ref preview renders, JSONL export writes lines. Extend the
  existing real-click e2e (`tests/test_ui_*`).

## Visual QA

Re-capture the four mockup states (`main_desktop_timeline`,
`filter_recording_sidebar`, `event_detail_inspector`, `timeline_filmstrip_focused`)
from the **real** window via `scripts/capture_bridge_tracer.py`, then
`scripts/visual_qa/visual_diff.py --config visual_diff_config.json`. Do not
weaken thresholds; use `visual_acceptance_spec.json` judgment (a real-widget
window won't be byte-identical to the painted mock — inspect diffs). Keep all
existing config entries.

## Git / worktrees (per Autonomous Execution Directive)

- Ai_Bridge: worktree `../Ai_Bridge__codex_trace` branch `codex/trace-api`.
- Bridge_Tracer: continue on `codex/bridge-tracer-ui-real` (or a fresh
  `codex/bridge-tracer-timeline`).
- Commit per workstream; merge `--no-ff` only when that repo's tests (+ visual QA
  for the tracer) pass. Suggested execution order: **A → B → C** (each
  independently testable; B can use a stub `/trace` server until A lands).

## Verification (end-to-end, real bridge)

1. `python -m pytest` green in both repos; tracer visual_diff 8/8 (or justified).
2. Bridge: `curl -H "Authorization: Bearer <token>" http://127.0.0.1:8765/trace/events`
   returns multi-category events; `/trace/events/stream` streams live.
3. Live app run: launch `py -m src.app.main`, Connect (default `127.0.0.1:8765`),
   Start → drive bridge traffic (a `/chat` call) → timeline shows **http + llm +
   tool + file** lanes populating live with connectors; click an event → inspector
   + raw JSON; apply a post-filter; export JSONL; Stop; Save/Load round-trip.
4. Opt-in live e2e (`tests/test_live_bridge_e2e.py`) extended to assert multiple
   categories appear (not just `llm`), run with `BRIDGE_TRACER_LIVE=1` +
   `AI_BRIDGE_ADMIN_TOKEN`.

## Notes / risks

- Large, two-repo effort — execute and merge in phases A→B→C so value lands
  incrementally and master is never left broken.
- SSE on a Qt thread: keep all widget mutation on the UI thread via signals;
  stop/join the worker on Stop and `closeEvent`.
- Don't log/store bearer tokens anywhere in the trace bus or events.