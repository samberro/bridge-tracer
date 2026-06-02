# Section 5 — Visual System, Theme, Layout & Motion (Task List)

**Owning plan section:** MASTER-PLAN §5 · **Phase:** 2 (visual pass) → 4 (polish) ·
**Read first:** `gfx design/REPORT.graphic-design.md` (all sections — this is the spec),
`product design/REPORT.product-design.md` P4/P5/P6/P7, `docs/diagnostic-shots/*`,
approved mockups `assets/mockups/bridge_tracer/`.

**Section goal:** a coherent, polished visual + motion system that matches the approved
mockups — consistent tokens, legible cards/lanes/connectors, discoverable splitters with
persisted layout, a real logs pane, a decluttered toolbar, and subtle 120–220ms motion
with a reduced-motion path. Validate against the 264-event screenshot, not sample data.

**Key files:** `src/ui/theme.py`, `src/ui/main_window.py` (`_STYLE`, builders),
`src/ui/timeline_view.py` (painters), new `src/ui/motion.py` (animate helper),
new `QSplitterHandle` subclass.

---

### T5.1 — Token system: fix collisions + de-hardcode
- **Objective:** single source of truth for colors; category == color holds at 8px.
- **Files:** `src/ui/theme.py`, `src/ui/timeline_view.py`, `src/ui/main_window.py`.
- **Steps:** add tokens per GFX §3 — `CARD_BG`, `CARD_BG_HOVER`, `BORDER_SOFT`,
  `ELEV_SEL_RING`, `OVERLAY_SCRIM`, `TEXT_FAINT`, `STATE_LIVE/LIVE_DIM/IDLE/WARN/ERROR/INFO`,
  `ACCENT`; **fix AUTH/PARSER collision** (PARSER → `#c084fc`); align `ERROR` to
  `STATE_ERROR`. Replace hard-coded hexes in `EventCardItem.paint` (`#0d1728`, `#ef4444`,
  `#d9e4ff`) and `_STYLE` with tokens.
- **Deliverable/Acceptance:** AUTH ≠ PARSER; no hard-coded category/state hexes in painters/QSS. **Deps:** none. **Parallel:** yes (foundation for the rest of §5).

### T5.2 — Event card visual states
- **Objective:** clear hierarchy + states (hover/selected/error/warning/new/muted).
- **Files:** `src/ui/timeline_view.py` (`EventCardItem.paint`).
- **Steps:** per GFX §5.2 — 4px category stripe, 13/600 title, 11 subtitle, 10 mono meta
  line (`200 · 231ms`); **solid** selection ring (`ELEV_SEL_RING`), explicit hover
  (`CARD_BG_HOVER`), error 6% red wash + flat warn glyph (not filled `!` bubble), warning
  underline, muted/ghost for filtered.
- **Deliverable/Acceptance:** category readable by color at 100% zoom; selection findable
  at zoom-out; hover present. **Deps:** T5.1. **Parallel:** with T2.* (coordinate file edits).

### T5.3 — Lane rail + remove centerlines + time ruler
- **Objective:** quiet, scannable lanes.
- **Files:** `src/ui/timeline_view.py` (`TimelineScene.drawBackground`).
- **Steps:** per GFX §5.1 — flat lane bands, 1px `BORDER_SOFT` lane boundaries (remove the
  colored dashed centerlines), left rail (dot + UPPERCASE 10px label + count chip),
  active-lane brightening, faint top time ruler with ticks.
- **Deliverable/Acceptance:** lanes read calm; empty gaps read as "quiet time"; labels legible. **Deps:** T5.1. **Parallel:** yes.

### T5.4 — Splitter grips + cursor
- **Objective:** make resize discoverable.
- **Files:** `src/ui/main_window.py` (`_STYLE` + a `QSplitterHandle` subclass).
- **Steps:** 8px handles; paint a center grip line + faint dots; hover/drag → `ACCENT`;
  split cursors; optional one-time first-run tint hint (reduced-motion = static).
- **Deliverable/Acceptance:** every handle visibly distinct at rest; hit area ≥8px. **Deps:** T5.1. **Parallel:** yes.

### T5.5 — Layout persistence + sizing/size-policies
- **Objective:** layout survives restart; panels breathe.
- **Files:** `src/ui/main_window.py` (`__init__`, `closeEvent`).
- **Steps:** `QSettings` save/restore of `workspace/surface/inspector` splitter state +
  window geometry; hard-coded `setSizes` become first-run defaults only. Replace fixed
  widths with min + `QSizePolicy.Expanding` where panels should grow; raise sensible mins.
- **Deliverable/Acceptance:** resize → restart → layout restored; panels resize proportionally. **Deps:** none. **Parallel:** yes (used by T3.1, T4.6).

### T5.6 — Logs: real resizable pane/drawer
- **Objective:** replace the dead 42px bar.
- **Files:** `src/ui/main_window.py` (`_build_logs_panel`).
- **Steps:** make logs a resizable splitter pane (min ~120px) OR a collapsible drawer
  (animated height) showing real `/logs` tail — mono rows, level-colored dot
  (`LEVEL_COLORS`), timestamp gutter; never ship a fake "click to expand".
- **Deliverable/Acceptance:** logs show real lines or the strip is absent; no non-functional affordance. **Deps:** T5.1. **Parallel:** yes.

### T5.7 — Toolbar declutter
- **Objective:** reduce the 15+ ungrouped controls.
- **Files:** `src/ui/main_window.py` (`_build_toolbar`).
- **Steps:** group into connection | recording | view clusters with separators/spacing
  (or an overflow menu); integrate the status pill (T1.3) and filter chips (T4.3).
- **Deliverable/Acceptance:** toolbar reads in clear groups; nothing crammed. **Deps:** T1.3, T4.3. **Parallel:** Phase 4.

### T5.8 — Motion system + reduced-motion helper
- **Objective:** one consistent, accessible motion layer.
- **Files:** new `src/ui/motion.py` (`animate(obj, prop, dur, easing)`), call sites.
- **Steps:** central helper honoring a `reduced_motion` setting (follow OS where
  detectable); implement the GFX §10 timing table (arrival 180ms, selection 140ms, hover
  120ms, fan-out 200ms, filter 160ms, REC pulse 1400ms loop, reconnect hairline, skeleton
  shimmer, count tick); every animation has an instant/static reduced-motion path.
- **Deliverable/Acceptance:** all animations route through `animate()`; reduced-motion
  degrades each to instant; nothing in the interaction path exceeds 220ms (loops excepted). **Deps:** T5.1. **Parallel:** yes (consumed by T2.3, T1.3/T5.9).

### T5.9 — Status-pill styling + live affordance
- **Objective:** the visual half of the live indicator (widget API from T1.3).
- **Files:** `src/ui/main_window.py` (status pill), `src/ui/motion.py`.
- **Steps:** style the pill per GFX §9.1 (state dot + text + count, SURFACE_ALT bg);
  breathing REC dot (1400ms), reconnecting blink, error shake, 2px live header hairline,
  digit-roll count tick — all via `animate()`/reduced-motion.
- **Deliverable/Acceptance:** during recording the live state is impossible to miss; reduced-motion = solid dot. **Deps:** T1.3, T5.8. **Parallel:** after those.

---

## Section is done when
- [ ] Tokens consistent; AUTH ≠ PARSER; no hard-coded category/state hexes.
- [ ] Cards/lanes/connectors match GFX spec and the mockups at 264 events.
- [ ] Splitters discoverable; layout + window geometry persist across restart.
- [ ] Logs pane is real and readable; no fake affordances.
- [ ] Toolbar grouped/decluttered; status pill integrated.
- [ ] Every animation routes through `animate()` with a reduced-motion path; ≤220ms in interaction path.
- [ ] Visual diff vs `assets/mockups/bridge_tracer/` acceptable.
