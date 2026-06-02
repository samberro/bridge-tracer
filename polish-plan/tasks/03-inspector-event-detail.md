# Section 3 — Inspector & Event Detail (Task List)

**Owning plan section:** MASTER-PLAN §3 · **Phase:** 3 ·
**Read first:** `product design/REPORT.product-design.md` §7/P3, `gfx design/REPORT.graphic-design.md` §6/P3, `docs/diagnostic-shots/event_detail_inspector.png`.

**Section goal:** a spacious, fast, readable inspector — two-column rows, accordion
sections, remembered width, lazy/bounded object tree, file-ref/image preview,
jump-to-event, and two-event compare.

**Key files:** `src/ui/main_window.py` (`_build_inspector`, `_refresh_inspector`,
`_populate_object_tree`), `src/ui/view_models.py` (`EventDetail`, `compare_event_details`),
`src/core/file_refs.py`, `src/bridge_client/client.py` (`fetch_file_ref`).

---

### T3.1 — Wider + remembered inspector width
- **Objective:** stop the ~300px squeeze.
- **Files:** `src/ui/main_window.py` (`_build_ui`).
- **Steps:** raise inspector min to ~440px (keep max 900); persist `workspace_splitter`
  width via `QSettings` (coordinate with T5.5); default ~480px.
- **Deliverable/Acceptance:** default ≥440px, survives restart (AC-5). **Deps:** T5.5 for persistence. **Parallel:** yes.

### T3.2 — Accordion sections + two-column rows
- **Objective:** readable hierarchy; sections that don't crush each other.
- **Files:** `src/ui/main_window.py` (`_build_inspector`, `_refresh_inspector`).
- **Steps:** replace fixed `inspector_splitter` sizes `[150,170,430]` with collapsible
  accordions (Title+badges always; Fields default open; Object open; Evaluate/Raw
  collapsed; remembered per session). Two-column key/value rows (96px UPPERCASE key
  gutter, mono values, 24px rows) per GFX §6.
- **Deliverable/Acceptance:** tool-call object tree shows ≥8 rows without scrolling at
  default height (AC-5); section collapse persists. **Deps:** T5.1 (tokens/QSS). **Parallel:** yes.

### T3.3 — Lazy / bounded object tree
- **Objective:** stop freezing on huge `details` payloads.
- **Files:** `src/ui/main_window.py` (`_populate_object_tree`, `_add_object_tree_children`).
- **Steps:** populate children on expand (lazy); cap initial depth/breadth with a
  "load more" affordance; keep pinned root + double-click-to-pin; add copy-path / copy-value.
- **Deliverable/Acceptance:** selecting an event with a large payload populates instantly;
  deep JSON expands on demand. **Deps:** none. **Parallel:** yes.

### T3.4 — File-ref / image preview (wire "Open File Ref")
- **Objective:** the dead button becomes a real preview.
- **Files:** `src/ui/main_window.py` (`file_ref_btn`), `src/core/file_refs.py`, `src/bridge_client/client.py`.
- **Steps:** wire `file_ref_btn` to `FileRefRetriever`/`fetch_file_ref`; render image
  refs as thumbnails (QPixmap) and text refs inline; handle missing/oversized refs gracefully.
- **Deliverable/Acceptance:** clicking a file ref shows a preview, not nothing; errors handled. **Deps:** none. **Parallel:** yes.

### T3.5 — Jump-to-event from inspector
- **Objective:** navigate from a related event back to the timeline.
- **Files:** `src/ui/main_window.py`, `src/ui/timeline_view.py`.
- **Steps:** add a "Jump to event" action and clickable related-event chips that frame +
  select the card (uses explicit-selection `ensureVisible`, per T2.7).
- **Deliverable/Acceptance:** Jump frames+selects the target card; off-screen targets scroll smoothly. **Deps:** T2.7. **Parallel:** after T2.7.

### T3.6 — Two-event compare + file diff
- **Objective:** surface the unused compare logic; add a simple diff for file events.
- **Files:** `src/ui/main_window.py`, `src/ui/view_models.py` (`compare_event_details`).
- **Steps:** add a Compare action (pick two events → side-by-side field/JSON diff using
  `compare_event_details`); for file-change events, a simple before/after text diff.
- **Deliverable/Acceptance:** compare panel shows differences for two selected events. **Deps:** T3.2 (layout). **Parallel:** Phase 4.

---

## Section is done when
- [ ] Inspector default ≥440px, remembered across restart (AC-5).
- [ ] Two-column accordion rows; ≥8 object rows at default height (AC-5).
- [ ] Lazy object tree never freezes on large payloads.
- [ ] File-ref/image preview works; no dead "Open File Ref".
- [ ] Jump-to-event and two-event compare work.
