# Section 6 — Threading & Performance (Task List)

**Owning plan section:** MASTER-PLAN §6 · **Phase:** 1 (A5) → 3 (async I/O) → 4 (perf guard) ·
**Read first:** `docs/diagnostic-baseline.md` (blocking-I/O findings, recorder race, rebuild timings).

**Section goal:** zero blocking I/O on the Qt GUI thread, a thread-safe recorder, and a
perf regression guard so the app stays smooth at 300+ events and never freezes on
connect/poll/save/load.

**Key files:** new `src/ui/async_runner.py`, `src/ui/controller.py`, `src/ui/main_window.py`,
`src/core/recorder.py`, `src/bridge_client/client.py`.

---

### T6.1 — Reusable background-call infrastructure
- **Objective:** one helper to run blocking calls off the GUI thread.
- **Files:** new `src/ui/async_runner.py`.
- **Steps:** `QThreadPool`/`QRunnable` (or QThread+worker) wrapper taking a callable,
  emitting `finished(result)` / `failed(exc)` via queued signals to the GUI; cancellation
  + in-flight guard. Unit-test offscreen.
- **Deliverable/Acceptance:** helper with tests; results marshalled to GUI thread safely. **Deps:** none. **Parallel:** yes (foundation for T6.2–T6.4).

### T6.2 — Async connect / trace_available
- **Objective:** Connect never freezes the window.
- **Files:** `src/ui/main_window.py` (`_on_connect`), `src/ui/controller.py` (`connect`, `trace_available`).
- **Steps:** run the blocking HTTP probe via T6.1; disable Connect + show "connecting…"
  (status pill, T1.3) while in flight; update on the result signal; surface 401/bad-URL errors.
- **Deliverable/Acceptance:** slow/unreachable bridge does not freeze the UI; error reason shown. **Deps:** T6.1, coordinate with T1.3. **Parallel:** Phase 3.

### T6.3 — Async log polling (fallback mode only)
- **Objective:** the (fallback-only) poll never blocks the GUI thread.
- **Files:** `src/ui/main_window.py` (`_poll_once`), `src/ui/controller.py` (`pull_logs`).
- **Steps:** dispatch the `/logs` fetch via T6.1; merge results on the result signal;
  guard overlapping in-flight polls. (Remember: poll runs ONLY in `AI_BRIDGE_RECORDING_FALLBACK`
  mode per §1; SSE mode is event-driven.)
- **Deliverable/Acceptance:** fallback polling never blocks; no overlapping polls. **Deps:** T6.1, T1.2. **Parallel:** Phase 3.

### T6.4 — Async save / load
- **Objective:** large recordings don't freeze save/load.
- **Files:** `src/ui/main_window.py` (`_on_save`, `_on_load`), `src/ui/controller.py`.
- **Steps:** run file I/O via T6.1 with a busy/disabled affordance; surface load errors
  (currently unsurfaced); add recents (coordinate with QoL).
- **Deliverable/Acceptance:** saving/loading a large recording keeps the UI responsive; load errors shown. **Deps:** T6.1. **Parallel:** Phase 3.

### T6.5 — Recorder thread-safety
- **Objective:** remove the feed/stop race between the SSE thread and GUI thread.
- **Files:** `src/core/recorder.py`.
- **Steps:** add a `threading.Lock` around `feed()` / state transitions so the
  check-then-append can't race; verify with a start/stop + feed stress loop.
- **Deliverable/Acceptance:** no lost/misrouted events under concurrent feed+stop; stress loop clean. **Deps:** coordinate with §1 (T1.1). **Parallel:** yes (Phase 1).

### T6.6 — Perf regression guard
- **Objective:** lock in responsiveness.
- **Files:** new `tests/test_perf_budget.py`.
- **Steps:** timed offscreen test asserting an incremental append + a filter keystroke at
  300+ events complete under a budget derived from the baseline (old full rebuild was
  ~59ms/1000 events).
- **Deliverable/Acceptance:** AC-11 — append/keystroke under budget; fails if perf regresses. **Deps:** T2.1, T4.1. **Parallel:** Phase 4. (Shared with §8.)

---

## Section is done when
- [ ] No blocking HTTP/file I/O on the GUI thread (connect/trace/poll/save/load).
- [ ] Recorder is thread-safe; feed+stop stress loop clean.
- [ ] Perf guard test green at 300+ events (AC-11).
- [ ] Slow/unreachable bridge and large save/load never freeze the window.
