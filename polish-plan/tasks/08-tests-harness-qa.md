# Section 8 — Tests, Capture Harness & QA (Task List)

**Owning plan section:** MASTER-PLAN §8 · **Phase:** 1 (green baseline) → 4 (full QA) ·
**Read first:** `docs/diagnostic-baseline.md` (19 failing tests, broken capture harness,
flaky leaked threads), `tests/conftest.py`, `scripts/live_smoke.py`, existing
`tests/test_ui_interactive_e2e.py`.

**Section goal:** a green test suite on a clean baseline, a working visual-capture harness,
and automated coverage for every feature — full-feature E2E (incl. live smoke at 300+
events), resize/layout-persistence, and a perf guard. So all other sections land on green
and stay green.

**Key files:** `scripts/capture_bridge_tracer.py`, `scripts/capture_ui_screenshots.py`,
`scripts/live_smoke.py`, `tests/` (multiple), `tests/conftest.py`.

---

### T8.1 — Repair the visual-capture harness
- **Objective:** `python scripts/capture_bridge_tracer.py` works again.
- **Files:** `scripts/capture_bridge_tracer.py`, `scripts/capture_ui_screenshots.py`.
- **Steps:** fix the `use_mockup_backdrop` / `BridgeTracerWindow` constructor mismatch to
  match the current window API; regenerate the 4 visual states.
- **Deliverable/Acceptance:** capture script exits 0 and writes all 4 state PNGs. **Deps:** none. **Parallel:** yes (Phase 1).

### T8.2 — Triage & update drifted tests
- **Objective:** stale tests reflect the current implementation.
- **Files:** `tests/test_ui_streaming.py`, `tests/test_recording_transport.py`, `tests/test_ui_app_window.py`, `tests/test_pull_logs.py`, `tests/test_capture_bridge_tracer.py`.
- **Steps:** update to current APIs — `SSEStreamWorker` (no `.isFinished()`,
  `threading.Thread`-based), `FakeSSEWorker.__init__` (`at` kwarg), removed window params.
  Coordinate with §1/§6 if those APIs change.
- **Deliverable/Acceptance:** drifted tests pass against current code. **Deps:** coordinate with T1.*, T6.5. **Parallel:** Phase 1.

### T8.3 — Fix the possibly-real failures
- **Objective:** fix actual bugs, don't just re-baseline.
- **Files:** `src/ui/main_window.py`, `src/ui/controller.py`, `src/ui/timeline_view.py`, relevant tests.
- **Steps:** `test_stop_halts_polling` (poll timer not halting), `...without_exposing_bearer_token`
  (token redaction — security), `...does_not_force_scroll_on_rebuild` (force-scroll on
  rebuild → fixed by T2.7). Also fix the flaky leaked-SSE-thread cross-test interference
  (ties to T1.1/T6.5).
- **Deliverable/Acceptance:** these tests pass deterministically; full suite green & stable across runs. **Deps:** T2.7, T1.1, T6.5. **Parallel:** Phase 1–2.

### T8.4 — Extend the live smoke harness
- **Objective:** a reusable live E2E at real volume.
- **Files:** `scripts/live_smoke.py`.
- **Steps:** parametrize bridge URL/token; assert the **append** path (post-T2.1) and
  event-count growth; drive a 300+-event run; optional non-offscreen mode + screenshot.
- **Deliverable/Acceptance:** live smoke passes against the running bridge with 300+ events; no leaked threads. **Deps:** T1.2, T2.1. **Parallel:** Phase 2–4.

### T8.5 — Full-feature offscreen E2E suite
- **Objective:** automated coverage of every feature.
- **Files:** new `tests/test_full_feature_e2e.py` (extend `tests/test_ui_interactive_e2e.py` patterns).
- **Steps:** `QTest`-driven offscreen flow with a fake SSE source: connect → start →
  live-append → search/filter → category toggles → run/session selector → select event →
  inspect (fields/object/raw/eval/file-ref) → pre-record filters → triggers → save → load
  → stop → close. Assert state + no exceptions + no token leak.
- **Deliverable/Acceptance:** every feature exercised; suite green. **Deps:** the features it tests (run last per area). **Parallel:** Phase 4.

### T8.6 — Resize / layout-persistence automation
- **Objective:** lock in §5 layout behavior.
- **Files:** new `tests/test_layout_resize.py`.
- **Steps:** programmatically set splitter sizes, resize the window, assert panels honor
  min/size-policies and that `QSettings` round-trips splitter state + geometry (T5.5).
- **Deliverable/Acceptance:** layout persists across a simulated restart; panels respect mins. **Deps:** T5.5. **Parallel:** Phase 4.

### T8.7 — Perf guard (shared with §6)
- **Objective:** prevent sluggishness regressions.
- **Files:** `tests/test_perf_budget.py` (same as T6.6).
- **Steps/Acceptance:** see T6.6 (append + filter keystroke under budget at 300+ events, AC-11). **Deps:** T2.1, T4.1. **Parallel:** Phase 4.

---

## Section is done when
- [ ] `python -m pytest -q` is green and stable across repeated runs (no flaky thread leaks).
- [ ] Visual capture harness works; regenerates the 4 states.
- [ ] Full-feature E2E (T8.5), resize (T8.6), and perf (T8.7) tests pass.
- [ ] Live smoke at 300+ events against the running bridge is clean (T8.4).
- [ ] The other sections' regression tests (T1.5, T2.*, T6.6) are green.
