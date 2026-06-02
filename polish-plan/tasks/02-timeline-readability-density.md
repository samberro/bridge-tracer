# Section 2 — Timeline Readability & Density (Task List)

**Owning plan section:** MASTER-PLAN §2 · **Phase:** 2 ·
**Read first:** `docs/diagnostic-shots/live_recording.png` (the stacked/sparse failure),
`product design/REPORT.product-design.md` §6/P2, `gfx design/REPORT.graphic-design.md` §5/P1/P6.

**Section goal:** 300+ live events stay readable — no overlapping cards, no dead gaps,
bursts collapse into informative collection cards that fan out on zoom, rendering is
incremental and bounded, and connectors are calm. Validate every change against the
264-event screenshot, NOT the 8-event sample.

**Key files:** `src/ui/timeline_view.py` (`_layout_events`, `populate_events`,
`EventCardItem`, `ConnectorItem`, `TimelineScene`), `src/ui/main_window.py` (rebuild plumbing).

---

### T2.1 — Incremental append API
- **Objective:** stop destroying/rebuilding the whole `QGraphicsScene` on every update.
- **Files:** `src/ui/timeline_view.py`, `src/ui/main_window.py`.
- **Steps:** add `TimelineView.append_events(new_events)` that adds only new cards/
  connectors to the existing scene (reuse `_layout_events` math) without a new
  `TimelineScene`; keep `populate_events` for full reloads (load/filter change). Route
  live streaming (T1.2 signal) through `append_events`; keep the 125ms timer as a
  coalescer, not the refresh trigger.
- **Deliverable:** incremental live rendering.
- **Acceptance:** live append frame-work stays well under the old ~59ms/1000-event full
  rebuild at 300+ events (AC-11); no flicker; selection preserved.
- **Deps:** T1.2. **Parallel:** core task for this section.

### T2.2 — X-axis modes (fit/time/log) + Fit + auto-follow
- **Objective:** kill overlapping stacks and dead gaps from raw wall-clock positioning.
- **Files:** `src/ui/timeline_view.py` (`_layout_events`), `src/ui/main_window.py` (toolbar).
- **Steps:** add x-axis `mode ∈ {fit, time, log}`; default `fit` = order/index spacing
  (equal counts → equal space); `log` compresses idle gaps; `time` keeps wall-clock.
  Keep real timestamps in tooltip/inspector/ruler ticks. Add a **Fit** action and
  **auto-follow newest** while recording with a **Jump to live** when the user scrolls back.
- **Deliverable:** readable default layout + Fit/Follow.
- **Acceptance:** 300+ events → no time-induced gap > 1.5 card-widths; Fit frames every
  event (AC-3). **Deps:** none (coordinate with T2.3). **Parallel:** yes.

### T2.3 — Collection cards + fan-out
- **Objective:** collapse same-lane x-collisions into one informative card that expands.
- **Files:** `src/ui/timeline_view.py` (new `CollectionCardItem`, `_collapse_dense()`).
- **Steps:** after layout, group lane events whose x overlaps at current zoom into a
  `CollectionCardItem` (stacked-paper visual + `+N` badge + category-dot chip row +
  **error precedence** so any error shows on the collapsed card). Click/zoom-in **fans**
  children into individual cards (spring ~180–220ms; reduced-motion instant via §5
  `animate()`); zoom/click-out collapses. Keep `populate_events` O(n); selection +
  connectors survive expand/collapse.
- **Deliverable:** working collection cards.
- **Acceptance:** at 264 events no two cards overlap; collapsed groups show errors
  without expanding; expand/collapse round-trips without losing selection (AC-3/AC-4).
- **Deps:** T2.2 (layout), §5 `animate()` (T5.8). **Parallel:** after T2.2.

### T2.4 — Item cull / cap + memory bound
- **Objective:** keep long recordings bounded.
- **Files:** `src/ui/timeline_view.py`, `src/core/recorder.py` (optional cap).
- **Steps:** configurable retained-item cap (ring buffer) with a "showing last N of M"
  hint; explicitly delete dropped `EventCardItem`s (disconnect signals, remove from
  scene) to free C++ objects; optional event windowing.
- **Deliverable:** bounded scene/memory.
- **Acceptance:** 5k-event stress stays responsive; no unbounded growth; no leaked items.
- **Deps:** T2.1. **Parallel:** after T2.1.

### T2.5 — Cache preview/title; remove compute from paint
- **Objective:** stop evaluating render rules / expanding JSON inside `paint()`.
- **Files:** `src/ui/timeline_view.py` (`EventCardItem`), `src/ui/render_rules.py`.
- **Steps:** memoize `preview_for_event`/`title_for_event` per event id (invalidate on
  render-rule change); compute card text once at item creation, not in `paint()`/`_tooltip_text()`.
- **Deliverable:** cheap paints.
- **Acceptance:** paint contains no JSON/AST work; scroll/zoom stays smooth at 300+ events.
- **Deps:** none. **Parallel:** yes (independent of T2.1).

### T2.6 — Connector discipline + thread-on-select
- **Objective:** end the spider-web at density.
- **Files:** `src/ui/timeline_view.py` (`ConnectorItem`, `_create_connectors`).
- **Steps:** 1px, below cards; inferred (dashed) at ~35% alpha, explicit (solid) ~55%;
  on selection, render only the selected event's run/request chain at full strength and
  drop others to ~12% or hide above a density threshold.
- **Deliverable:** calm connectors.
- **Acceptance:** selecting a card highlights only its thread; no full-strength web at 264 events.
- **Deps:** none. **Parallel:** yes.

### T2.7 — No force-scroll on background rebuild
- **Objective:** background refresh must not move the viewport.
- **Files:** `src/ui/timeline_view.py` (`set_selected_event`/`populate_events`).
- **Steps:** only call `ensureVisible` on explicit user selection / Jump, never on a
  plain rebuild/append. (Fixes the flagged `does_not_force_scroll_on_rebuild` test.)
- **Deliverable:** stable viewport during live updates.
- **Acceptance:** AC-6 — background refresh never scrolls; selection does. **Deps:** none. **Parallel:** yes.

---

## Section is done when
- [ ] 300+ events: zero overlapping cards, no gap > 1.5 card-widths, Fit frames all (AC-3).
- [ ] Collection cards expand/collapse with animation, keep selection, show errors collapsed (AC-4).
- [ ] Live append cheaper than old full rebuild at 300+ (AC-11); bounded memory.
- [ ] Connectors calm; thread-on-select works.
- [ ] Background refresh never force-scrolls (AC-6).
