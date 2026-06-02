# Section 1 — Recording, Live State & Reliability (Task List)

**Owning plan section:** MASTER-PLAN §1 · **Phase:** 1 (top priority) ·
**Read first:** `docs/diagnostic-baseline.md` (recording bugs), `product design/REPORT.product-design.md` §1/§9, `gfx design/REPORT.graphic-design.md` §9.

**Section goal:** recording "just works" without polling — live events appear in the
UI within 250ms, the connection auto-reconnects on drop, and the recording state is
always obvious. No token leak. This is the trust core; nothing else matters until it holds.

**Key files:** `src/ui/controller.py`, `src/ui/main_window.py`, `src/ui/interactive_window.py`, `src/core/recorder.py`.

---

### T1.1 — SSE worker survives idle + auto-reconnects
- **Objective:** stop the SSE worker dying on the 1s read timeout; treat idle as
  normal; reconnect on real disconnect.
- **Files:** `src/ui/controller.py` (`SSEStreamWorker`), `src/bridge_client/stream.py`.
- **Steps:** in `SSEStreamWorker.run`, catch `httpx.ReadTimeout`/idle inside the read
  loop and continue (re-check `_stop_event`) instead of letting it exit; keep a
  short-ish read timeout only for stop responsiveness; on genuine disconnect/HTTP
  error, reconnect with backoff (e.g. 0.5→1→2→5s capped), emitting a new
  `reconnecting`/`reconnected` signal; stop cleanly on `_stop_event`.
- **Deliverable:** worker that runs ≥60s through idle gaps and recovers after the
  bridge is killed and restarted; new `state` signals.
- **Acceptance:** with a 25s+ effective idle tolerance the worker stays alive and
  keeps ingesting; killing the bridge 5s then restoring auto-reconnects (AC-2). No
  leaked threads after stop/close.
- **Deps:** coordinate with T1.3 (consumes reconnect signals), T6.5 (recorder lock). **Parallel:** yes.

### T1.2 — Event-driven UI refresh (remove poll-as-refresh)
- **Objective:** the SSE→recorder→UI path updates the timeline without the poll timer.
- **Files:** `src/ui/controller.py`, `src/ui/main_window.py`, `src/ui/interactive_window.py`.
- **Steps:** add a Qt signal `events_changed` (or `events_ingested(count)`) on
  `BridgeTracerController`; emit it from `_on_stream_event` (and the `Recorder.on_event`
  hook) when new events are recorded, coalesced. In the window, connect it to the
  existing debounced rebuild (`_schedule_rebuild_from_controller` / 125ms timer) — and
  in Phase 2 to `TimelineView.append_events` (T2.1). Move the SSE-first start logic out
  of the `interactive_window.py` monkeypatch into the base `MainWindow._on_start` so the
  base no longer unconditionally starts the poll timer (`main_window.py:1071`); poll
  timer runs ONLY when `controller.is_log_fallback` is True.
- **Deliverable:** recording with polling off updates the UI live.
- **Acceptance:** SSE on, poll timer stopped → one new chat message makes the UI
  `event_count()` and a new card appear within 250ms; **0 `/logs` calls** (AC-1). The
  `event_count()==0`-while-recording bug cannot reproduce.
- **Deps:** pairs with T1.1; integrates with T2.1 in Phase 2. **Parallel:** yes (Phase 1 wire to full rebuild; swap to append in Phase 2).

### T1.3 — Recording state machine + status pill
- **Objective:** a single always-visible source of truth for recording/connection state.
- **Files:** `src/ui/main_window.py` (replace `status_label`), `src/ui/controller.py` (`ControllerStatus`).
- **Steps:** model states idle → connecting → recording ⇄ reconnecting → stopping →
  stopped, plus → failed. Replace the plain `status_label` with a **status-pill widget**
  (state dot + text + `· {count} events · last {Ns} ago`). Drive it from controller
  signals (status change + `events_changed` + reconnect from T1.1). Mirror in the
  sidebar counters. Visual styling/animation handled in §5 (T5.9) — expose the widget
  API and state here.
- **Deliverable:** pill reflecting every state; "last event Ns ago" counter.
- **Acceptance:** pill reflects idle/connecting/recording/reconnecting/stopped/failed
  within 250ms; failed shows the bridge error reason (AC-7). No token in pill text (AC-12).
- **Deps:** T1.1, T1.2; visual polish in T5.9. **Parallel:** after T1.1/T1.2 land state signals.

### T1.4 — Empty / loading / disconnected / error states
- **Objective:** never show a frozen black canvas or fake data; explain every non-active state.
- **Files:** `src/ui/main_window.py`, `src/ui/timeline_view.py`.
- **Steps:** stop seeding 8 sample events when empty (`MainWindow.__init__`) — show a
  **friendly empty state** ("Connect a bridge to begin tracing" + Connect/Record
  actions, ghosted lane scaffold). During the first SSE snapshot show **skeleton lanes**.
  On disconnect, keep the last frame + a slim dismissible **error/disconnect banner**
  with Retry; on reconnecting, a quiet WARN hairline. (Exact visuals in §5/GFX §9; build
  the widgets + wiring here.)
- **Deliverable:** distinct empty/loading/disconnected/error UI.
- **Acceptance:** first run with no events shows guidance + primary actions, never
  unlabeled sample data (AC-9); disconnect shows banner + keeps cards; reconnect clears it.
- **Deps:** T1.1 (state signals), T1.3. **Parallel:** partial.

### T1.5 — Live recording regression test
- **Objective:** lock in T1.1+T1.2 so recording can't silently break again.
- **Files:** `tests/test_live_recording_refresh.py` (new), `scripts/live_smoke.py` (extend).
- **Steps:** offscreen test with a fake SSE source: record with polling disabled,
  assert new events reach the **UI model** (not just the recorder) after ingest, that a
  mid-recording event appears, 0 `/logs` calls, idle gap doesn't kill the worker, and
  recording ends clean with no leaked threads. Extend `scripts/live_smoke.py` to assert
  count growth against the live bridge.
- **Deliverable:** passing regression test(s).
- **Acceptance:** test fails on today's code, passes after T1.1+T1.2.
- **Deps:** T1.1, T1.2. **Parallel:** after those. (Also referenced by §8.)

---

## Section is done when
- [ ] Recording works SSE-only: new bridge event in UI ≤250ms, 0 `/logs` calls (AC-1).
- [ ] Auto-reconnect after a 5s bridge drop; no lost events on resume (AC-2).
- [ ] Status pill reflects all 6 states ≤250ms incl. failure reason (AC-7).
- [ ] Friendly empty/loading/disconnected/error states; no unlabeled sample data (AC-9).
- [ ] No token leak in any status/label/log (AC-12).
- [ ] Regression test (T1.5) green; no leaked SSE threads after close.
