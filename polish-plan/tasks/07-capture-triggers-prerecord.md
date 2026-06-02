# Section 7 — Capture Config, Pre-record Filters & Triggers (Task List)

**Owning plan section:** MASTER-PLAN §7 · **Phase:** 3 ·
**Read first:** `product design/REPORT.product-design.md` P6/§8, `docs/diagnostic-baseline.md` (stub findings), `src/core/filters.py`, `src/core/triggers.py`.

**Section goal:** every visible control is real or explicitly disabled+labeled — pre-record
filters actually scope what is captured, the trigger matrix runs real start/stop logic,
and the sidebar connection panel reflects true status. No fake data, no silent no-ops.

**Key files:** `src/ui/main_window.py` (`_build_sidebar`, `_build_trigger_matrix`),
`src/ui/controller.py`, `src/core/filters.py` (`PreRecordFilter`), `src/core/triggers.py`
(`StartTrigger`, `StopTrigger`, `TriggerEvaluator`).

---

### T7.1 — Wire pre-record filters
- **Objective:** the sidebar pre-record checkboxes actually filter capture.
- **Files:** `src/ui/main_window.py` (`_build_sidebar`), `src/ui/controller.py`, `src/core/filters.py`.
- **Steps:** connect the checkboxes ("Only selected session", "Only LLM traffic", "Tool
  calls", "Errors", etc.) to a `PreRecordFilter` applied at `controller.start_recording` /
  recorder ingest (`_on_stream_event`). "Record everything" disables the others. Add tests.
- **Deliverable/Acceptance:** with "Only LLM traffic" on, non-LLM events are not recorded;
  toggling updates capture for the next recording. **Deps:** none (logic exists). **Parallel:** yes.

### T7.2 — Wire recording trigger matrix
- **Objective:** real start/stop triggers, not decorative cards.
- **Files:** `src/ui/main_window.py` (`_build_trigger_matrix`), `src/ui/controller.py`, `src/core/triggers.py`.
- **Steps:** replace hardcoded demo cards with real `StartTrigger`/`StopTrigger` wired to
  `TriggerEvaluator` (endpoint-hit start, session-id-appears, error-occurs auto-capture,
  tool-called, stop-after-N-events, stop-after-timeout). Toggles enable/disable real
  triggers and persist (`QSettings`). Add tests.
- **Deliverable/Acceptance:** "stop after N events" actually stops recording at N;
  "auto-capture on error" starts on first error; toggles persist. **Deps:** T7.1 path. **Parallel:** Phase 3.

### T7.3 — Bind connection panel
- **Objective:** the sidebar Connection section shows real data.
- **Files:** `src/ui/main_window.py` (`_build_sidebar`).
- **Steps:** replace the hardcoded `"http://localhost:8080"` / masked token / `"valid"`
  with the real bridge URL, token-presence (masked), live `controller.status`, and last
  error. Never render the token itself (AC-12).
- **Deliverable/Acceptance:** connection panel mirrors actual state; no fake strings; no token leak. **Deps:** T1.3 (status). **Parallel:** yes.

### T7.4 — Disable + label not-yet-functional controls
- **Objective:** nothing looks interactive but silently no-ops.
- **Files:** `src/ui/main_window.py`.
- **Steps:** audit all visible controls; anything not yet wired gets disabled + a "soon"
  affordance (tooltip/label). Applies until its real task lands.
- **Deliverable/Acceptance:** AC-8 — no visible control shows fake data or silently no-ops. **Deps:** after T7.1–T7.3. **Parallel:** Phase 3 tail.

---

## Section is done when
- [ ] Pre-record filters actually scope what is recorded (tests pass).
- [ ] Trigger matrix runs real start/stop logic; toggles persist (tests pass).
- [ ] Connection panel reflects real status; no fake data; no token leak (AC-8, AC-12).
- [ ] Any not-yet-functional control is explicitly disabled + labeled.
