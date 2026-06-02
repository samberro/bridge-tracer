# Bridge Tracer — Master Polish Plan (Consolidated)

**Goal:** take Bridge Tracer from "half-built, crashes, recording shows nothing,
unreadable at volume" to a **finished, polished, fully functional product** — a calm,
trustworthy desktop flight-recorder for `Ai_Bridge` that a developer can launch,
connect, record, and read at hundreds of live events without confusion.

This plan consolidates **three sources of truth**:
1. **Live smoke-test findings** — `docs/diagnostic-baseline.md` (recording bugs, the
   stacked-events "dumpster fire", broken-then-fixed theme, perf, drifted tests).
2. **Product Design report** — `product design/REPORT.product-design.md` (flows,
   states, feature behavior spec, pain points P1–P8, acceptance criteria AC-1…12).
3. **Graphic & Motion report** — `gfx design/REPORT.graphic-design.md` (tokens,
   typography, card/lane/connector visuals, status pill, motion P1–P10).

Work is organized into **8 areas (Sections 1–8)**. Each has its own executable
task-list document under `polish-plan/tasks/`. The plan is sequenced into 4 phases;
within a phase, sections run largely in parallel. The plan is **complete only when
every section's "Section is done when" checklist passes** (see §Definition of Done).

---

## End-state in one paragraph (the north star)

The user launches Bridge Tracer to a calm dark control-room with a friendly empty
state ("Connect a bridge to begin"). They connect; a **breathing REC pill** + live
counter make it impossible to miss that recording is working. Events stream in
**incrementally**; bursts collapse into informative **collection cards** that fan out
on zoom, so 300+ events stay readable with no overlapping stacks and no dead gaps.
Color means category/severity only. One click opens a **spacious two-column
inspector** (fields / object tree / raw / evaluate / file preview / compare). Filters
are obvious, fast, reversible chips; a run/session selector scopes the view. A flaky
bridge auto-reconnects with a quiet banner, never a freeze or a crash. Subtle
120–220ms motion explains every state change. Nothing visible is fake or no-ops. The
app is keyboard-navigable, layout persists across restarts, and the test/visual
harness is green.

---

## Cross-cutting issues → which section owns the fix

| Issue (source) | Owning section |
|---|---|
| SSE worker dies on 1s timeout, no reconnect (smoke H1) | §1 Recording & Live State |
| Live events never reach UI when not polling (smoke H2) | §1 |
| No live affordance / state machine (Product §9, GFX P2) | §1 |
| Empty/loading/disconnected states undefined (Product P7, GFX P9) | §1 + §5 |
| Stacked/sparse timeline at volume (smoke B6, Product P2, GFX P1) | §2 Timeline |
| Full-scene rebuild ~59ms/1k; no append/cull (smoke B1–B3) | §2 |
| Connector spider-web (GFX P6) | §2 |
| Cramped inspector; lazy/bounded tree (Product P3, smoke C3, GFX P3) | §3 Inspector |
| File-ref preview / compare / jump-to-event (Product §7) | §3 |
| Slow search; O(n) selection (smoke C1/C2) | §4 Filtering & Nav |
| Filter chips, run/session selector, keyboard nav (Product P8/§8/QoL) | §4 |
| Broken global QSS (FIXED D1); tokens/typography/motion (GFX all) | §5 Visual System |
| Splitter affordance + layout persistence (Product P5, smoke D2/D3) | §5 |
| Logs strip dead 42px bar (Product P4, GFX P4) | §5 |
| Toolbar clutter; sizing/size-policies (smoke D2/D4) | §5 |
| Blocking I/O on GUI thread: connect/poll/save/load (smoke A1–A4) | §6 Threading/Perf |
| Recorder feed race (smoke A5) | §6 (coordinated with §1) |
| Pre-record filters & trigger matrix are stubs (smoke E1/E2, Product P6) | §7 Capture/Triggers |
| Hardcoded sidebar connection panel (Product P6) | §7 |
| Capture harness broken; 19 drifted tests; missing E2E/perf tests (smoke F/G) | §8 Tests/QA |

---

## The 8 sections (each links to its task document)

### §1 — Recording, Live State & Reliability  → `tasks/01-recording-live-state.md`
- **Issues:** SSE dies on idle timeout; no recorder→UI refresh without polling; no
  reconnect; no visible recording state machine; no empty/loading/disconnected UX.
- **End result:** recording "just works" without polling — new events appear in the UI
  within 250ms; auto-reconnect on drop; a breathing REC pill + counter + "last event
  Ns ago"; friendly empty/loading/disconnected/error states; no token leak.
- **How:** event-driven `events_changed` signal; survive-idle + reconnect in
  `SSEStreamWorker`; status-pill widget + state machine; empty/skeleton/banner widgets.

### §2 — Timeline Readability & Density  → `tasks/02-timeline-readability-density.md`
- **Issues:** wall-clock x-axis → overlapping stacks + dead gaps; full-scene rebuild;
  no cull/cap; preview computed in paint; connector spider-web.
- **End result:** 300+ events readable — no overlaps, no voids; collection cards that
  fan out on zoom; incremental append; bounded memory; calm connectors (thread-on-select).
- **How:** index/fit x-axis + `_collapse_dense()` + `CollectionCardItem`; `append_events`;
  ring-buffer cull; cache preview/title; connector alpha/weight discipline + focus.

### §3 — Inspector & Event Detail  → `tasks/03-inspector-event-detail.md`
- **Issues:** cramped ~300px inspector; flat hierarchy; unbounded object-tree walk;
  dead "Open File Ref"; no jump-to-event; no compare/diff.
- **End result:** spacious two-column inspector with accordion sections, remembered
  width, lazy/bounded object tree, image/file-ref preview, jump-to-event, compare.
- **How:** widen+persist; accordion sections; two-column row styling; lazy expand;
  wire FileRef preview; `compare_event_details` panel; jump action.

### §4 — Filtering, Search & Navigation  → `tasks/04-filtering-search-navigation.md`
- **Issues:** json.dumps per event per keystroke; O(n) selection sync; no chips; no
  run/session selector; no keyboard nav; no filter presets.
- **End result:** instant debounced search on cached haystack; O(1) selection; active
  removable filter chips; run/session scope selector; full keyboard navigation; presets.
- **How:** precompute/caches; id→item map; chip bar; sidebar selector; `QShortcut` set.

### §5 — Visual System, Theme, Layout & Motion  → `tasks/05-visual-system-theme-motion.md`
- **Issues:** token drift (AUTH==PARSER; hardcoded hexes); flat cards; stripey lanes;
  faint splitters; dead logs bar; cluttered toolbar; no persisted layout; no motion system.
- **End result:** coherent token system; polished cards/lanes/connectors; discoverable
  splitters + persisted layout; real logs drawer; decluttered toolbar; 120–220ms motion
  with reduced-motion; matches approved mockups.
- **How:** extend `theme.py`; rework `_STYLE` + painters; `QSplitterHandle` grips +
  `QSettings`; logs pane; toolbar grouping; central `animate()` helper.

### §6 — Threading & Performance  → `tasks/06-threading-performance.md`
- **Issues:** synchronous httpx on GUI thread (connect/trace/poll/save/load); recorder
  feed race; no perf guard.
- **End result:** zero blocking I/O on the GUI thread; thread-safe recorder; perf
  regression test; smooth at 300+ events.
- **How:** `async_runner` (QThreadPool/QRunnable); move connect/poll/save/load off-thread;
  recorder lock; perf budget test.

### §7 — Capture Config, Pre-record Filters & Triggers  → `tasks/07-capture-triggers-prerecord.md`
- **Issues:** pre-record filter checkboxes no-op; trigger matrix decorative; sidebar
  connection panel hardcoded/fake.
- **End result:** pre-record filters actually scope capture; real start/stop triggers;
  connection panel bound to real status — nothing fake or silently no-op.
- **How:** wire `core/filters.py` + `core/triggers.py`; bind sidebar to `controller.status`;
  disable+label anything not yet functional.

### §8 — Tests, Capture Harness & QA  → `tasks/08-tests-harness-qa.md`
- **Issues:** capture script throws; 19 drifted/failing tests; flaky leaked SSE threads;
  no full-feature E2E, resize, or perf tests.
- **End result:** green suite on a clean baseline; working visual capture; automated
  full-feature E2E (incl. live smoke), resize, and perf-guard tests.
- **How:** fix `capture_bridge_tracer.py`; triage/update drifted tests; fix real
  failures; extend `scripts/live_smoke.py`; add E2E/resize/perf tests.

---

## Phasing & sequencing

**Phase 1 — Make it trustworthy & green (blockers).**
- §1 (H1+H2 recording works without polling; reconnect; live pill) — TOP PRIORITY.
- §6 A5 (recorder lock) — coordinate with §1.
- §8 G1/G2/G3 (harness + suite green) so later work lands on green.
- §5 first-pass: empty-state + token fixes that §1 needs.

**Phase 2 — Make it readable (the volume problem).**
- §2 (incremental append, index/fit axis, collection cards, cull, connectors).
- §5 visual pass for cards/lanes/connectors/status-pill/motion (pairs with §2 & §1).

**Phase 3 — Make it deep & usable.**
- §3 inspector; §4 filtering/search/nav; §7 pre-record filters/triggers/connection.
- §6 async I/O (A1–A4) for connect/poll/save/load.

**Phase 4 — Polish & close.**
- Remaining §5 motion/microinteractions, logs drawer, splitter grips, toolbar declutter.
- §4 presets/keyboard finishing; §3 compare/pop-out.
- §8 full E2E + resize + perf guards green; live smoke at 300+ events.
- Final visual QA vs mockups; Definition of Done sweep.

**Parallelization:** §1, §8, §6-A5 start immediately (Phase 1). §2 and the §5 visual
pass run in parallel in Phase 2 (coordinate edits to `timeline_view.py`/`theme.py`).
§3, §4, §7 are largely independent in Phase 3 (main shared file is `main_window.py`
— sequence those edits or keep diffs small). §8 test additions trail each section.

---

## Definition of Done (the app is "finished & polished")

The plan reaches the end goal when ALL of these hold (each maps to section task docs):
1. **Recording works without polling** — SSE-only; a new bridge message appears in the
   UI within 250ms; 0 `/logs` calls; auto-reconnect after a 5s drop (AC-1, AC-2). [§1]
2. **Readable at volume** — 300+ live events: zero overlapping cards, no dead gaps,
   collection cards fan out smoothly, errors visible without expanding (AC-3, AC-4). [§2]
3. **Live state is obvious** — breathing REC pill + counter + state machine reflect
   idle/connecting/recording/reconnecting/stopped/failed within 250ms (AC-7). [§1/§5]
4. **Inspector is spacious** — two-column, ≥440px, remembered; lazy tree; file preview;
   jump-to-event; compare (AC-5). [§3]
5. **Filtering/nav** — chips, run/session selector, debounced search, O(1) selection,
   keyboard nav (AC-10). [§4]
6. **Visual polish** — tokens consistent (AUTH≠PARSER), cards/lanes/connectors per
   spec, splitters discoverable + layout persists, real logs pane, motion with
   reduced-motion. Matches mockups. [§5]
7. **No blocking I/O** on the GUI thread; thread-safe recorder; perf guard green (AC-11). [§6]
8. **Nothing fake** — pre-record filters/triggers/connection panel real or explicitly
   disabled+labeled (AC-8); friendly empty/first-run (AC-9). [§7/§1]
9. **No token leak** anywhere (AC-12). [cross-cutting]
10. **Green QA** — full suite passes; visual capture works; automated full-feature E2E,
    resize, and perf tests pass; live smoke at 300+ events is clean. [§8]

A final **live E2E at 300+ events against the running bridge** (extend
`scripts/live_smoke.py`) plus a **visual diff vs `assets/mockups/bridge_tracer/`** is
the acceptance gate for "polished".
