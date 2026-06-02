# Bridge Tracer — Product Design Report

Author: Product Designer subagent · Date: 2026-06-02
Sources of truth: `docs/diagnostic-baseline.md`, `docs/diagnostic-shots/*`, live source under `src/ui` + `src/core`.
Scope: layout, hierarchy, flows, states, interaction, behavior, acceptance criteria. Exact colors/type/icon art/motion-curve values are deferred to the graphic designer (motion needs flagged inline as `[motion]`).

> **The four user-requested items are called out explicitly:**
> **[REQ-1] End-state vision** — §1, §4, §5.
> **[REQ-2] Full feature inventory + behavior spec** — §13 (per-state behavior, Implemented/Partial/Missing).
> **[REQ-3] Current usability pain points** — §3 (includes the "dumpster fire" and "recording shows nothing").
> **[REQ-4] 2–3 buildable ideas per pain point, ranked impact vs effort** — §3 under each pain point.

---

## 1. Product diagnosis — [REQ-1 vision anchor]

Bridge Tracer is a desktop "flight recorder" for the `Ai_Bridge` backend. It connects to a bridge, records the live event stream (HTTP / LLM / tool / file / parser / error / session / etc.), and lays those events on a **lane-per-category timeline** so a developer can see *what the AI actually did*, in order, and inspect any single event down to raw JSON.

The skeleton is right: real SSE ingestion works end-to-end (264 live events ingested in the smoke test), the lane timeline + connector graph is a good mental model, the inspector has the right building blocks (fields / evaluate / object tree / raw JSON), and post-record filtering works. The product fails at three things that matter most during real debugging:

1. **You cannot tell it is working.** Live events reach the recorder but never reach the UI model when polling is off, and the SSE worker silently dies after a 1s read timeout. The user sees a frozen, empty canvas while events pour in. This is a **broken mental model**, not a cosmetic bug.
2. **It collapses under real volume.** At ~270 events the timeline renders overlapping/stacked cards in a couple of time clusters with the rest of the canvas empty (`live_recording.png`). A design that works at 8 events and dies at 270 is a failed design.
3. **It feels cramped and unfinished where the work happens.** The inspector is narrow, the logs strip is a 42px dead bar, splitter handles are hard to find, and several visible controls are stubs (sidebar connection values hardcoded, pre-record filter checkboxes do nothing, trigger matrix decorative).

**Design north star:** *trustworthy, calm, readable, obvious.* The user should never wonder whether recording is working, should scan hundreds of events without zoom archaeology, and reach any event detail in one click.

---

## 2. User goals

| # | Goal | Today | Target |
|---|------|-------|--------|
| G1 | Connect and confirm I am receiving events | Ambiguous tiny status string | Connection + live pulse impossible to miss |
| G2 | Record while I reproduce a bug | Records, but UI shows nothing live | Live count + newest event visibly streaming |
| G3 | Scan what happened, spot the anomaly | Unreadable at volume | Density-managed lanes; errors pop |
| G4 | Drill into one event | Possible but cramped | Roomy inspector, fast scan, copy/jump |
| G5 | Narrow to a subset and undo it | Works, not obviously reversible | Fast, reversible, explains what changed |
| G6 | Save/share/re-open a recording | Works (JSON) | Keep; recents + summary header |
| G7 | Survive a flaky connection | Worker dies, no reconnect | Auto-reconnect with visible state |

---

## 3. Major usability failures + fixes — [REQ-3] + [REQ-4]

Each pain point lists 2–3 buildable ideas ranked impact vs effort (★ impact, ⚙ effort; prefer high-★/low-⚙ first).

### P1 — "Recording shows nothing" (CRITICAL, broken mental model)
Evidence: `diagnostic-baseline.md` recording+filtering live test. SSE worker dies on a 1s read timeout with no reconnect (`controller.py:79 timeout=1.0`); and with polling disabled in SSE mode the UI never syncs recorder→model (`main_window.py` refreshes only via `_poll_timer` → `_schedule_rebuild_from_controller`, which `interactive_window._on_start_sse_first` stops). Result: `controller.events`→304 while `event_count()`→0.

- **Idea A (★★★ / ⚙⚙) — Event-driven UI refresh.** Controller emits a Qt signal (`events_changed`) on ingest; window connects it to a debounced incremental refresh (reuse the 125ms `_timeline_rebuild_timer`). Removes polling-as-refresh. *Highest-leverage fix in the product.*
- **Idea B (★★★ / ⚙) — Survive-idle SSE + auto-reconnect.** Treat read timeout as "idle, keep listening" (loop on timeout in `SSEStreamWorker.run`); on real disconnect retry with backoff, emit `reconnecting`. Pairs with §9.
- **Idea C (★★ / ⚙) — Live heartbeat.** Always-visible "● RECORDING · 304 · last 0.4s ago" pill driven by the refresh signal `[motion: subtle pulse]`.

**Acceptance:** SSE on, no poll timer → one new chat message makes count+newest card appear within 250ms; bridge killed 5s then restored auto-reconnects; toolbar always shows time-since-last-event.

### P2 — Timeline "dumpster fire" at real volume (HIGH)
Evidence: `live_recording.png` (264 events → overlapping stacks + empty canvas). `TimelineView._layout_events` positions x by absolute wall-clock (`px_per_second` from full span) with only a per-lane min-spacing fallback, so bursts overlap and idle gaps waste space.

- **Idea A (★★★ / ⚙) — Index/log time x-axis (default "fit to events").** Replace raw wall-clock x with order-based or log-compressed axis so equal event counts get equal space; keep real timestamps in tooltip/inspector/axis ticks; add a "Fit" action. Lowest effort, biggest readability win.
- **Idea B (★★★ / ⚙⚙) — Collection cards (the seed idea).** When N cards in a lane would overlap, render one **collection card** (count + category-mix mini-bar, e.g. "12 events · 3 errors"). Click/zoom **fans them out into individual cards with a spring animation** `[motion: spring fan-out]`; zoom back collapses. Collision detection in `_layout_events`; a `CollectionCardItem` sibling of `EventCardItem`. Scales because the scene holds only visible-resolution items.
- **Idea C (★★ / ⚙⚙) — Lane density rail + minimap.** Per-lane heat rail showing bursts + draggable viewport minimap. Additive nav aid, not an overlap fix → rank third.

**Acceptance:** 300+ events → no two cards overlap at default zoom; idle gaps never exceed ~1.5 card-widths; "Fit" frames every event; collection cards expand/collapse smoothly and keep selection.

### P3 — Inspector is cramped (HIGH, task blocker)
Evidence: `diagnostic-baseline.md` sizing (inspector min 300/max 900); `live_recording.png` right panel. Fields, evaluate, object tree, raw JSON fight for ~300px.

- **Idea A (★★ / ⚙) — Wider default + remembered width.** Default ~440–520px (already maxes at 900), persist splitter size via QSettings, raise the min. One-line changes in `_build_ui`.
- **Idea B (★★ / ⚙⚙) — Collapsible sections.** Replace fixed `inspector_splitter` sizes `[150,170,430]` with accordions (Fields / Evaluate / Object / Raw); default Fields+Object open.
- **Idea C (★★★ / ⚙⚙⚙) — Pop-out / docked-wide inspector.** Detach into its own window or half-width for deep JSON, then re-dock. Highest impact, highest effort — after A/B.

**Acceptance:** default width ≥440px, survives restart; tool-call object tree shows ≥8 rows without scrolling at default height; section collapse persists per session.

### P4 — Logs strip is a dead 42px bar (MEDIUM)
Evidence: `logs_panel.setFixedHeight(42)` + a "click to expand" label with no handler (`_build_logs_panel`). Looks interactive, is not.

- **Idea A (★★ / ⚙) — Make it expand.** Real collapsible drawer (40px ↔ 240px) reusing the `_set_filter_panel_visible` animation, showing the live `/logs` tail.
- **Idea B (★★ / ⚙⚙) — Promote logs to a bottom tab.** Peer of Timeline/Event List with full height + search.
- **Idea C (★ / ⚙) — Remove until real.** Hide rather than show a fake affordance.

**Acceptance:** strip either shows real log lines or is absent; no non-functional "click to expand" ships.

### P5 — Resize handles undiscoverable (MEDIUM)
Evidence: handles were 4px/unstyled; D1 set 6px+hover. Still relies on a tiny "drag dividers to resize" hint.

- **Idea A (★★ / ⚙) — Persistent grip + bigger hit area.** Visible grip glyph centered on each handle, hit area ~8–10px; drop the text hint `[graphic designer: handle art]`.
- **Idea B (★ / ⚙) — Double-click reset.** Double-click resets to default sizes.
- **Idea C (★ / ⚙⚙) — Layout presets.** "Layout" menu (Default / Wide inspector / Timeline focus) mapping to `set_visual_state`.

**Acceptance:** every handle visibly distinct at rest; hit area ≥8px; double-click resets.

### P6 — Stub controls erode trust (MEDIUM)
Evidence: sidebar Connection rows hardcoded (`"http://localhost:8080"`, masked token, `"valid"`, `_build_sidebar`); pre-record filter checkboxes have no handlers; trigger matrix decorative (`_build_trigger_matrix`).

- **Idea A (★★ / ⚙) — Bind connection panel.** Real URL, masked token presence, real `controller.status` + last error.
- **Idea B (★★ / ⚙⚙) — Wire pre-record filters or mark "coming soon".** Connect to `src/core/filters.py` or disable+label.
- **Idea C (★ / ⚙⚙⚙) — Make triggers real.** Functional start/stop rules via `src/core/triggers.py` (stop-after-N, timeout, auto-capture-on-error). Gate behind MVP.

**Acceptance:** no visible control shows fake data or silently no-ops; not-yet-functional controls are explicitly disabled with a "soon" affordance.

### P7 — Empty / first-run state undefined (MEDIUM)
Evidence: window seeds 8 sample events when none exist (`MainWindow.__init__`); empty scene is a bare 900x420 rect (`populate_events`).

- **Idea A (★★ / ⚙) — Real empty state.** Centered "Connect a bridge and press Record to capture events" + the two primary actions instead of fake data.
- **Idea B (★ / ⚙) — Label sample as demo.** If kept, badge "Sample" + "Clear sample".

**Acceptance:** first run with no events shows guidance + primary actions, never unlabeled fake events.

### P8 — Filtering not obviously reversible / explained (LOW–MEDIUM)
Evidence: post-filters work (`_filtered_events`) and status shows "N shown", but the panel is a transient drawer with no per-filter undo.

- **Idea A (★★ / ⚙) — Active-filter chips + one-click clear.** Removable chips ("LLM only ✕", "search: tool ✕") in the toolbar; reuse existing filter state.
- **Idea B (★ / ⚙) — Result delta toast.** Brief "showing 42 of 304" near the timeline `[motion: fade]`.

**Acceptance:** every active filter is a removable chip; clearing one restores exactly that dimension; counts reconcile.

---

## 4. Proposed design direction — [REQ-1]

1. **Liveness is first-class, always-on.** State pill (idle / recording ● / reconnecting ↻ / stopped / failed) + live counter + "last event Ns ago" live in the toolbar. Status is never inferred from an empty canvas.
2. **Density is managed, not ignored.** Timeline defaults to "fit to events" on an index/log axis, collapses bursts into collection cards, instantiates only visible-resolution items. Empty space is fine; *wasted* space is not.
3. **Progressive disclosure over clutter.** Lanes → cards → collection cards → inspector → raw JSON. Default view is useful with zero config; advanced controls (render rules, triggers, evaluate) are one click away.

---

## 5. Core screen layout — [REQ-1 ideal anatomy]

```
Toolbar:  Title  [URL] [token]  Connect | ● RECORDING 304 · last 0.4s · [Stop]
          Save Load | Filters (chips) | RenderRules | Zoom - 100% + Fit | status
Sidebar (optional)   |  Center tabs: Timeline · Event List · Logs   | Inspector
  Connection         |   density rail (per-lane heat + burst counts) | Title+badges
  Recording          |   HTTP/LLM/TOOL/ERR lanes, fit-to-events x    | Fields
  Pre-filters        |   [minimap viewport]                          | Object
                     |                                               | Evaluate / Raw
Logs drawer (collapsed 40px <-> expanded 240px)
```

- **Toolbar** = identity + connection + live state + global actions. Live pill is the anchor of trust (P1).
- **Sidebar** optional/collapsed by default (space → timeline); bound connection info + pre-record filters (P6).
- **Center** tabbed: Timeline (default), Event List (existing tree), Logs (promoted, P4); density rail above canvas; minimap at volume (P2-C).
- **Inspector** wider default, accordion sections, remembered width (P3).
- **Logs** real collapsible drawer, not a dead bar (P4).

---

## 6. Timeline behavior — engineering-facing spec

**Layout model (replaces `_layout_events`):**
- x-axis `mode in {fit, time, log}`; default `fit` = monotonic index spacing per global order (equal counts → equal space, kills overlap + dead gaps). `time` keeps wall-clock; `log` compresses idle gaps. Real timestamp in tooltip/inspector/axis ticks.
- y-axis: lane per active category (keep `_active_lanes`); request/response micro-offset fine (`_lane_offset`).
- **Collision → collection.** In a lane, if next card overlaps previous right edge at current zoom, accumulate into a `CollectionCardItem` until a gap reappears.
- **Expand/collapse.** Click collection or zoom past threshold → spring fan-out `[motion]`; collapse reverses. Selection + connectors survive.
- **Incremental append (perf).** Full rebuild ~59ms/1000 events every 125ms live (`diagnostic-baseline.md`). Append new cards; re-layout only the affected lane tail. Keep debounce as coalescer, not refresh trigger.
- **No force-scroll.** `set_selected_event` calls `ensureVisible` on every rebuild (flagged test `does_not_force_scroll_on_rebuild`). Only `ensureVisible` on explicit user selection.

**Default view:** Fit-to-events, newest lane-tail in view, auto-follow newest while recording (with "jump to live" if user scrolls back).

| State | Timeline behavior |
|---|---|
| Empty | Centered guidance + primary actions (P7) |
| Loading/connecting | Skeleton lanes + "connecting…" shimmer `[motion]` |
| Active/recording | Cards stream in (append), auto-follow, pill pulses |
| Disconnected | Last frame frozen + amber "connection lost" banner |
| Reconnecting | "reconnecting…" + retry count `[motion: ↻]` |
| Error | Red banner + bridge error + Retry |

P2 acceptance applies.

---

## 7. Inspector behavior — spec

- **Sections** (accordion, remembered): Title+badges (always), Fields (default open), Object View (open), Evaluate (collapsed), Raw JSON (collapsed).
- **Fields** from `selected_detail().fields`; errors surface level/message at top in error color.
- **Object tree** keeps pinned root + double-click-to-pin (`_pin_tree_field`); add copy-path / copy-value.
- **Evaluate** keeps DSL (`$.details.status_code`, `last_message(obj)`, `path(...)`) + Save Rule; never auto-rebuilds the whole timeline (already patched in interactive_window — keep).
- **Actions:** Copy JSON (exists), **Jump to event** (new — frame+select card), Open File Ref (wire it; currently dead).
- **Empty:** "No event selected — click a card or list row."

**Acceptance:** see P3; selection populates Title/Fields/Object within one frame; Jump frames+selects the card.

---

## 8. Filters / search behavior — spec

- **Two tiers, clearly separated:** *Pre-record* (what is captured — sidebar, stubs P6) vs *Post-record* (what is shown — drawer, works). Label so "not captured" is not confused with "not shown".
- **Active-filter chips** in toolbar (P8): each removable; "Clear all" → `set(EventCategory)` + empty text + errors-off (existing `_clear_post_filters`).
- **Search** full-haystack (summary/type/run/request/details/refs — `_filtered_events`); debounce ~150ms; show "N of M".
- **Reversibility:** non-destructive on `model.events`; clearing restores instantly.

---

## 9. Recording / live-state behavior — spec (the trust core)

State machine, always visible in toolbar pill:
idle → connecting → recording <-> reconnecting → stopping → stopped, plus → failed from any.

| State | Pill | Behavior |
|---|---|---|
| idle | Idle | Start enabled, Stop disabled |
| connecting | Connecting… | spinner; cancel available |
| recording | ● Recording · N · last Ns | live append, auto-follow, pulse `[motion]` |
| reconnecting | ↻ Reconnecting (k) | keep last frame, backoff retry, banner |
| stopping | Stopping… | flush → stopped |
| stopped | Stopped · N | Start re-enabled; frozen for review |
| failed | Failed: reason | error banner + Retry; never silent |

**Wiring:** controller emits on ingest → event-driven refresh (P1-A); SSE read-timeout = idle, real drop → reconnect (P1-B, fixes `controller.py:79`); "last event Ns ago" counter (P1-C); no token in any status string (keep `without_exposing_bearer_token` green).

---

## 10. Quality-of-life backlog (ranked)

1. Live pill + "last event Ns ago" (P1-C).
2. Active-filter chips (P8-A).
3. "Jump to event" from inspector (§7).
4. Remembered splitter/inspector widths (P3-A, P5).
5. "Fit" / "Jump to live" buttons (P2-A, §6).
6. Visible splitter grips + double-click reset (P5).
7. Real empty/first-run state (P7).
8. Logs drawer that actually expands (P4-A).
9. Recents for Save/Load + recording summary header.
10. Keyboard: up/down prev/next event, Enter focus inspector, / focus search, F fit, L jump-to-live, Esc clear selection, Space start/stop.

---

## 11. MVP vs polish split

**MVP (trust + readability core):**
- P1 A+B+C — event-driven refresh, survive-idle/reconnect, live pill. *(without this nothing else matters)*
- P2 A (+B) — index/fit axis + collection cards; incremental append.
- P3 A — wider/remembered inspector.
- §9 visible state machine; §6 no-force-scroll fix.
- P6 A — bind connection panel; disable fake controls.
- P7 A — real empty state.
- Repair capture harness + triage stale tests (`diagnostic-baseline.md` NEW finding) so UX work lands on green.

**Polish:** P2-C minimap/density rail, P3-B/C accordions + pop-out, P4 logs drawer/tab, P5 grips/presets, P8 chips/toasts, P6-C real triggers, QoL 9–10, motion refinement.

---

## 12. Acceptance criteria (consolidated, testable)

- **AC-1 (P1):** SSE on, poll timer stopped → one new bridge event appears in UI (count+card) within 250ms. *(regression for `event_count()==0`.)*
- **AC-2 (P1):** Bridge dropped 5s then restored → recording→reconnecting→recording automatically; no lost events on resume.
- **AC-3 (P2):** 300+ events → zero overlapping cards at default zoom; no time-induced gap > 1.5 card-widths; Fit frames all.
- **AC-4 (P2):** Collection card expand/collapse round-trips without losing selection; animates `[motion]`.
- **AC-5 (P3):** Inspector default >=440px, persists across restart; tool-call object tree >=8 rows at default height.
- **AC-6 (§6):** Background refresh never scrolls; only explicit selection calls `ensureVisible`.
- **AC-7 (§9):** Pill reflects idle/connecting/recording/reconnecting/stopped/failed within 250ms; failure shows reason.
- **AC-8 (P6):** No visible control shows fake data or silently no-ops; non-functional controls disabled+labeled.
- **AC-9 (P7):** First run with no events shows guidance + primary actions, no unlabeled sample data.
- **AC-10 (P8):** Every active filter is a removable chip; removing one restores that dimension; counts reconcile.
- **AC-11 (perf):** Live append keeps frame work well under old ~59ms/1000-event full rebuild at 300+ events.
- **AC-12 (security):** No status/label/log path renders the bearer token (keep `without_exposing_bearer_token` green).

---

## 13. Full feature inventory + behavior spec — [REQ-2]

Status: **Implemented** = works as a feature · **Partial** = present but buggy/cramped/stubbed · **Missing** = needed, not built.

| Feature | Status | States | Inputs/Outputs · Edge · Keyboard | Spec / fix |
|---|---|---|---|---|
| Connect to bridge | Partial | active pill; error reason needed; disconnected explicit | URL+token → `controller.connect` (redacts token). Edge: 401/bad URL must surface. Enter=connect | Bind real status (P6-A); show error reason |
| Start/Stop recording | Partial | recording ● / stopped; reconnecting needed | Buttons → start/stop. Edge: SSE dies silently (P1) | Event-driven refresh + reconnect (P1); pill (§9). Space |
| Live SSE ingestion | Partial | active; dies on 1s timeout | SSE → recorder. Edge: timeout treated fatal (`controller.py:79`) | Survive-idle + reconnect (P1-B) |
| Live UI refresh | Missing/broken | should stream into UI | recorder→model never syncs w/o poll | `events_changed` signal → debounced append (P1-A) |
| Log-poll fallback | Implemented | active when `AI_BRIDGE_RECORDING_FALLBACK` | `/logs` → `pull_logs`. 0 calls in SSE mode (correct) | Keep |
| Timeline lanes | Implemented | empty bare rect (fix); active lanes per category | events → `populate_events` | Real empty (P7); keep lanes |
| Timeline density at volume | Partial/fails | active: overlap/stack at ~270 | wall-clock x overlaps bursts (`_layout_events`) | Index/fit axis + collection cards (P2) |
| Event cards | Implemented | selected dashed ring; error red | click → `event_selected`; elide long text | Keep; feed from collection on expand |
| Connectors (parent/run) | Implemented | from parent_id + inferred run/request | missing parents → inferred dashed | Keep; recompute on expand |
| Collection/burst cards | Missing | collapsed count → fan-out | overlap → CollectionCardItem | Build (P2-B) |
| Zoom | Implemented | 35–220%, Ctrl+wheel, +/- | `set_zoom_percent` | Add Fit / Jump-to-live (P2-A) |
| Pan | Implemented | ScrollHandDrag cursors | — | Keep |
| Minimap / density rail | Missing | nav aid at volume | viewport + per-lane heat | Build (P2-C, polish) |
| Event List (tree) | Implemented | category/event/level cols, colored | selection syncs timeline+inspector | Keep; add sort/filter parity |
| Logs panel | Partial/dead | 42px bar, fake "click to expand" | no expand handler | Real drawer/tab (P4) |
| Inspector: Fields | Partial/cramped | empty "No event selected" | `selected_detail().fields` → rows | Wider + accordion (P3) |
| Inspector: Object tree | Implemented | pinned + object root; parses nested JSON | double-click pins | Add copy-path/value |
| Inspector: Raw JSON | Implemented | full `model_dump` | Copy works | Keep |
| Inspector: Evaluate DSL | Implemented | expr → result; Save Rule | `$.path`/`last_message`/`path()`; bad → "unable to evaluate" | Keep; no full rebuild on eval (patched) |
| Render/Pin rules | Implemented | dialog CRUD + reset | `RenderSettingsDialog` → card preview/pins | Keep; show where active |
| Copy JSON | Implemented | clipboard | `_copy_selected_json` | Keep |
| Open File Ref | Missing/dead | should open/preview ref | button no handler | Wire to FileRef retrieve/preview |
| Jump to event from inspector | Missing | frame+select | — | Build (§7) |
| Post-record filters | Implemented | drawer; categories/search/errors | `_filtered_events`; "N shown" | Add chips (P8) |
| Filter reversibility (chips) | Missing | per-filter undo | — | Build (P8-A) |
| Pre-record filters | Partial/stub | checkboxes do nothing | no handlers | Wire `core/filters.py` or disable+label (P6-B) |
| Recording triggers | Partial/decorative | static ON/OFF labels | no logic | Wire `core/triggers.py` (P6-C, polish) |
| Save recording | Implemented | JSON dialog | `save_recording` | Add recents |
| Load recording | Implemented | JSON dialog → rebuild | returns errors (unsurfaced) | Surface load errors; recents |
| Connection panel (sidebar) | Partial/hardcoded | fake URL/token/auth | static strings | Bind to `controller.status` (P6-A) |
| Recording counters (sidebar) | Implemented | state + count | `_refresh_controls` | Keep; mirror pill |
| Visual-state presets | Implemented (internal) | 4 layouts via `set_visual_state` | tests/captures | Expose as Layout menu (P5-C) |
| Theming/QSS | Implemented (D1 fixed) | dark theme | `_STYLE` now `.format()`-ed | Keep; graphic pass |
| Splitter resize | Partial | 6px+hover, low discoverability | text hint only | Grips + reset + persist (P5) |
| Empty / first-run | Missing | seeds fake sample events | `build_sample_events` | Real empty (P7) |
| Reconnect / failure UX | Missing | no reconnecting/failed surface | — | State machine + banners (§9) |
| Keyboard navigation | Missing | global shortcuts | only Ctrl+wheel zoom | Add shortcut set (QoL 10) |
| Capture/test harness | Partial/broken | screenshot TypeError; 19 failing tests | stale `use_mockup_backdrop` param | Repair + triage (MVP) |

---

### Appendix — files this design touches
- `src/ui/main_window.py` — layout, toolbar pill, inspector, logs drawer, empty state, filter chips, sidebar binding.
- `src/ui/timeline_view.py` — `_layout_events` axis modes, collection cards, incremental append, no-force-scroll, fit/jump-to-live.
- `src/ui/controller.py` — `events_changed` signal, survive-idle/reconnect, `SSEStreamWorker.run` timeout handling.
- `src/ui/interactive_window.py` — wire event-driven refresh in place of `_poll_timer`.
- `src/ui/view_models.py` — inspector detail/fields (accordion source).
- `src/core/filters.py`, `src/core/triggers.py` — pre-record filters and real triggers (P6).
- `scripts/capture_bridge_tracer.py` + tests — harness repair (MVP gate).
