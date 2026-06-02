# Section 4 — Filtering, Search & Navigation (Task List)

**Owning plan section:** MASTER-PLAN §4 · **Phase:** 3 (finishing in 4) ·
**Read first:** `product design/REPORT.product-design.md` §8/P8/QoL, `gfx design/REPORT.graphic-design.md` §7, `docs/diagnostic-baseline.md` (perf hotspots C1/C2).

**Section goal:** filtering and navigation feel instant, reversible, and obvious —
debounced search over a cached haystack, O(1) selection sync, active removable filter
chips, a run/session scope selector, full keyboard navigation, and saved filter presets.

**Key files:** `src/ui/main_window.py` (`_filtered_events`, `_on_post_filter_changed`,
`_sync_event_list_selection`, `_populate_events_list`, toolbar), `src/core/schemas.py`.

---

### T4.1 — Cached search haystack + debounced search
- **Objective:** stop `json.dumps`-ing every event on every keystroke/rebuild.
- **Files:** `src/ui/main_window.py` (`_filtered_events`), event ingest path.
- **Steps:** precompute each event's lowercased search string once (cache by event id;
  build on ingest); use it in `_filtered_events`. Debounce `post_search_edit.textChanged`
  (~150–200ms) before triggering a rebuild.
- **Deliverable/Acceptance:** typing in search is smooth at 300+ events; results show "N
  of M". **Deps:** none. **Parallel:** yes.

### T4.2 — O(1) tree selection
- **Objective:** kill the linear scan in selection sync.
- **Files:** `src/ui/main_window.py` (`_populate_events_list`, `_sync_event_list_selection`).
- **Steps:** maintain `dict[event_id → QTreeWidgetItem]` when populating the list; use it
  in `_sync_event_list_selection` instead of looping `topLevelItem`.
- **Deliverable/Acceptance:** selecting any event is O(1); no lag at volume. **Deps:** none. **Parallel:** yes.

### T4.3 — Active-filter chips + clear
- **Objective:** make active filters visible and individually reversible.
- **Files:** `src/ui/main_window.py` (toolbar/filter area).
- **Steps:** render each active filter as a removable chip ("LLM only ✕", "search: tool
  ✕", "errors only ✕"); removing one restores exactly that dimension; "Clear all" maps to
  `_clear_post_filters`. Visual styling per GFX §7 (T5 coordination).
- **Deliverable/Acceptance:** every active filter is a removable chip; counts reconcile
  (AC-10). **Deps:** T5.1 (chip styling). **Parallel:** yes.

### T4.4 — Run / session selector
- **Objective:** scope the timeline by run_id / session_id.
- **Files:** `src/ui/main_window.py` (sidebar), `src/ui/view_models.py`, `_filtered_events`.
- **Steps:** derive the set of active `run_id`/`session_id` from `model.events`; add a
  sidebar selector (combo or list); selecting one filters the timeline (integrate into
  the filter pipeline). Updates live as new runs appear.
- **Deliverable/Acceptance:** selecting a run/session shows only its events; "All" resets. **Deps:** T4.1 (filter path). **Parallel:** after T4.1.

### T4.5 — Keyboard navigation
- **Objective:** power-user navigation without the mouse.
- **Files:** `src/ui/main_window.py` (`QShortcut`s).
- **Steps:** add shortcuts: ↑/↓ prev/next event, Enter focus inspector, `/` focus search,
  `F` fit, `L` jump-to-live, `Esc` clear selection, `Space` start/stop. Document them.
- **Deliverable/Acceptance:** all shortcuts work and don't conflict; discoverable via tooltip/help. **Deps:** T2.2 (Fit/Live). **Parallel:** Phase 4.

### T4.6 — Filter presets
- **Objective:** save/restore filter combinations.
- **Files:** `src/ui/main_window.py`, `QSettings`.
- **Steps:** save current filter set (categories/search/errors/run-session) as a named
  preset; list + apply + delete; persist via `QSettings`.
- **Deliverable/Acceptance:** a saved preset restores the exact filter state across restart. **Deps:** T4.3, T5.5. **Parallel:** Phase 4.

---

## Section is done when
- [ ] Search is debounced over a cached haystack; smooth at 300+ events.
- [ ] Selection sync is O(1).
- [ ] Active filters are removable chips; removing one restores that dimension (AC-10).
- [ ] Run/session selector scopes the view.
- [ ] Keyboard navigation set works; filter presets persist.
