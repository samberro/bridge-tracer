# Bridge Tracer — Graphic & Motion Design Report

Author: Graphic & Motion Designer subagent
Date: 2026-06-02
Scope: color / typography / spacing / iconography / component treatments / motion. Layout structure & flows are owned by the product designer — this report specifies how things *look and behave*, not where panels go.

Source of truth used:
- `docs/diagnostic-baseline.md` (smoke-test root causes; 264 live events; sizing)
- Screenshots: `docs/diagnostic-shots/after_d1_main_desktop.png` (current dark look), `docs/diagnostic-shots/live_recording.png` (264-event stacked failure), `docs/diagnostic-shots/event_detail_inspector.png` (cramped inspector)
- Approved mockups: `assets/mockups/bridge_tracer/{main_desktop_timeline,event_detail_inspector,filter_recording_sidebar,timeline_filmstrip_focused}.png` (+ `svg/`)
- Code: `src/ui/theme.py`, `src/ui/main_window.py` (`_STYLE`), `src/ui/timeline_view.py`

All specs below are buildable in PySide6/Qt: QSS, `QPainter` in `EventCardItem.paint` / `TimelineScene.drawBackground`, and `QPropertyAnimation`/`QVariantAnimation` (the codebase already uses `QPropertyAnimation` + `QEasingCurve`, e.g. `main_window.py:904` filter panel at 180ms — motion specs here are consistent with that).

---

## 0. The four user-requested items, called out explicitly

- **REQUESTED ITEM 1 — "Where the app should be":** Section 2 (Art direction) + Section 13 (North-star summary).
- **REQUESTED ITEM 2 — "Every visual feature/component, how it looks & behaves":** Sections 3–11 (tokens, type, timeline cards + dense treatment, lanes, connectors, inspector, filter/sidebar, splitters, live/recording, empty/loading/error/disconnected, motion, microinteractions, reduced-motion) with hex tokens, px, and ms.
- **REQUESTED ITEM 3 — "Current visual pain points":** Section 1 (Visual diagnosis), grounded in the screenshots. Includes the stacked-events unreadability (P1) and weak live-state affordance (P2) plus the full set.
- **REQUESTED ITEM 4 — "2–3 ideas per pain point":** Section 14 (Pain-point remedies), 2–3 ranked ideas for every pain point, including the stacked-events "collection card" fan-out.

---

## 1. Visual diagnosis (current pain points, grounded in screenshots)

Ranked by user impact. Each is tied to what is visible in the shots / measured in the baseline.

**P1 — Timeline is unreadable at real volume (CRITICAL).**
`docs/diagnostic-shots/live_recording.png` (264 real events): cards collapse into 2–3 overlapping stacks in burst clusters while >70% of the canvas is empty. Root cause is in `timeline_view.py:_layout_events` — x is `min_ts`-relative wall-clock (`px_per_second`) with only a per-lane min-spacing fallback (`132/190px`), so bursts pile up and idle gaps waste space. Same-second events literally paint on top of each other; titles/subtitles are lost.

**P2 — Live / recording state has weak affordance (CRITICAL).**
The mockups show a status *pill* with a colored dot ("token/auth: valid · ws connected"). The build renders a plain `QLabel#status_label` text string (`main_window.py:516`, `:1172`). There is no persistent "we are LIVE" signal, no arrival pulse, no reconnect/error color. During recording the screen looks identical to idle — the single highest-frequency thing the user needs to track is invisible.

**P3 — Inspector is cramped and low-hierarchy.**
`event_detail_inspector.png` + baseline `inspector=(min 300)`. Key/value rows have little vertical rhythm, section headers (`inspector_section`) do not separate from values, the raw-JSON box is short. The mockup inspector is far more readable (clear `KEY  value` two-column rows, generous section spacing). Current build is tight and gray-on-gray.

**P4 — Logs strip is unreadably small.**
`logs_panel.setFixedHeight(42)` (`main_window.py:441`). ~1 line; during live tracing logs are effectively decorative.

**P5 — Splitter / resize affordance is faint.**
D1 raised handles to 6px (`_STYLE` `QSplitter::handle` `#1b2940`, hover `#2f5f9b`). It reads as a near-invisible seam against `SURFACE` — users do not discover panels resize. No grip texture.

**P6 — Connectors add noise at density.**
`ConnectorItem` draws cubic beziers for every parent/child AND inferred run/request pair (`_create_connectors`). At 264 events this is a spider-web. 1.25px in category color, no fade/under-layer discipline; competes with cards.

**P7 — Card internal hierarchy is flat.**
`EventCardItem.paint`: 5px stripe + 8px dot + bold 9pt title + 8pt muted subtitle. The error ring (`#ef4444`) + filled `!` bubble is the only strong state; selection is a dashed `#d9e4ff` outline hard to find at zoom-out. No hover state, no severity tint, no timestamp/duration micro-line.

**P8 — Lane labels & banding are low-contrast and "stripey".**
`TimelineScene.drawBackground`: alternating `#0d1424`/`#0a1020` bands + per-lane dashed center line in category color + uppercase label + count. The colored centerline through every lane competes with cards; label/count typography undersized vs mockup left rail.

**P9 — No first-run / empty / loading / disconnected visual language.**
Empty scene is `setSceneRect(0,0,900,420)` on `BACKGROUND` — a black void. No "connect to begin", no skeleton during first SSE snapshot, no disconnected banner. Unfriendly before configuration.

**P10 — Token / palette drift between code and mockup.**
Card body hard-coded `#0d1728`, error ring `#ef4444`, selection `#d9e4ff` — none in `theme.py`. AUTH `#a78bfa` and PARSER `#a78bfa` are identical; LLM `#818cf8` adjacent. Undermines "color == category" scanning.

---

## 2. Art direction — where Bridge Tracer should land

**One-line intent:** *A calm, technical control room.* Dark, low-noise, high-legibility; color is reserved almost entirely for meaning (category + severity + live state), never decoration. A precise instrument that stays quiet until something happens, then tells you clearly and briefly.

Principles:
- **Ink, not neon.** Deep desaturated navy field; saturated hue only on category accents, severity, live indicator. No glow, no text gradients, no scanline/hacker tropes.
- **Hierarchy by weight & space, not lines.** Prefer spacing, type weight, one accent over borders/dividers. Remove competing lines (lane centerlines, excess connectors) so cards read first.
- **Legible at 300+.** Every density decision validated against the 264-event shot, not the 8-event sample.
- **Motion explains state, then leaves.** 120–220ms, responsive easing, never blocks reading, always has a reduced-motion equivalent.
- **Friendly, not childish.** Warmth from rounded radii (10–16px), soft surfaces, polite empty state, gentle arrival motion — not mascots/bounce/bright color.

Target = the approved mockups: clean status pill, swimlanes with a quiet left rail, category-dot cards with title + subtitle, a spacious two-column inspector, toggle-pill filters/triggers.

---

## 3. Design tokens (extend `src/ui/theme.py`)

Keep existing names; add the roles below so painters and QSS stop hard-coding hexes. All dark-theme.

### 3.1 Surfaces & structure
```python
BACKGROUND    = "#08101f"   # app field / scene
SURFACE       = "#0e1728"   # panels (sidebar/inspector/logs)
SURFACE_DARK  = "#071020"   # wells (scrollbar track, code box)
SURFACE_ALT   = "#101b2d"   # raised / hover surface
CARD_BG       = "#0d1728"   # event card body (NEW token; was hard-coded in paint)
CARD_BG_HOVER = "#122036"   # card hover body (NEW)
BORDER        = "#22324c"   # default 1px border
BORDER_SOFT   = "#1a2740"   # quiet dividers / lane edges (NEW)
OVERLAY_SCRIM = "#040a14cc" # 80% scrim for modal/empty overlays (NEW)
ELEV_SEL_RING = "#d9e4ff"   # selection ring (NEW token; was hard-coded)
```

### 3.2 Text roles (existing kept)
```python
TEXT       = "#e6e9f0"   # primary
TEXT_MUTED = "#b9c1d1"   # secondary / subtitles
TEXT_DIM   = "#8390a5"   # tertiary / metadata, lane labels
TEXT_FAINT = "#5c6678"   # disabled / placeholder (NEW; matches QSS :disabled)
```

### 3.3 State roles (NEW — semantic, not category)
```python
STATE_LIVE     = "#22c55e"  # recording / connected (green)
STATE_LIVE_DIM = "#16a34a"  # live, low-emphasis
STATE_IDLE     = "#64748b"  # stopped / ready (slate)
STATE_WARN     = "#facc15"  # reconnecting / degraded
STATE_ERROR    = "#ff5d5d"  # error / disconnected (softened from #ef4444)
STATE_INFO     = "#38bdf8"  # neutral notice
ACCENT         = "#5b8def"  # primary action / focus ring (calm blue, NEW)
```

### 3.4 Category colors — keep roles, fix the two collisions
`AUTH` and `PARSER` are both `#a78bfa` (`theme.py:19,25`). Re-separate so hue == category survives at 8px:
```python
HTTP:        "#38bdf8"  # cyan      (keep)
LLM:         "#818cf8"  # indigo    (keep)
TOOL:        "#fb923c"  # orange    (keep)
MCP:         "#f472b6"  # pink      (keep)
FILE:        "#34d399"  # green     (keep)
SESSION:     "#2dd4bf"  # teal      (keep)
PERFORMANCE: "#facc15"  # amber     (keep)
ERROR:       "#ff5d5d"  # red       (align to STATE_ERROR)
AUTH:        "#a78bfa"  # violet    (keep)
PARSER:      "#c084fc"  # CHANGED — was #a78bfa, now lighter magenta-violet
SYSTEM:      "#9aa4b2"  # grey      (keep)
CONFIG:      "#64748b"  # slate     (keep)
```
Rule: a category accent appears as (a) the 4–5px left stripe, (b) the status dot, (c) the connector color — never as a card-body fill (bodies stay `CARD_BG`). Keeps the canvas calm while preserving instant category scanning.

### 3.5 Spacing scale (4px base) & radii
```
space:  xs 4 . sm 8 . md 12 . lg 16 . xl 24 . 2xl 32
radius: pill 999 . card 11 . panel 16 . well 8 . chip 8
border: hairline 1px . focus 2px
```

### 3.6 Elevation note (Qt has no shadows)
Simulate elevation by layered fills + a 1px lighter top edge, not blur. Raised card = `CARD_BG` body + 1px `BORDER` + (hover) a 1px inner highlight at top in `BORDER` lightened ~12%. Selection adds the `ELEV_SEL_RING` outline. No drop shadows, no glow.

---

## 4. Typography

Single UI family, mono for payloads (already: Segoe UI in cards, Consolas in `raw_json_box`).

| Role | Family | Size / weight | Color | Use |
|------|--------|---------------|-------|-----|
| Display | Segoe UI Semibold | 18px / 600 | TEXT | Panel titles ("Event Inspector") |
| Title | Segoe UI Semibold | 13px / 600 | TEXT | Card title, section heads |
| Body | Segoe UI | 12px / 400 | TEXT | Inspector values, controls |
| Subtitle | Segoe UI | 11px / 400 | TEXT_MUTED | Card subtitle, helper text |
| Label/meta | Segoe UI | 10px / 600, +0.4px tracking, UPPERCASE | TEXT_DIM | Lane labels, key column, eyebrows |
| Count badge | Segoe UI Semibold | 10px / 600 | TEXT | Collection-card count, lane count |
| Mono | Consolas / Cascadia Mono | 11px / 400 | TEXT | Raw JSON, ids, durations |

Rules: card title 13/600 (up from 9pt) so titles win over connectors; mono for every exact token/id/duration (run_id, request_id, `231ms`) so values align. One trailing ellipsis only; never mid-word wrap in cards. Tabular figures for counts/durations so digits do not jitter during live updates.

---

## 5. Timeline visual system

### 5.1 Lane / swimlane styling (`TimelineScene.drawBackground`)
- Replace alternating `#0d1424`/`#0a1020` bands + colored dashed centerline with a **quiet rail**:
  - Lane band: flat `BACKGROUND`; separate lanes with one 1px `BORDER_SOFT` line at the lane boundary (not a colored centerline through the middle). Remove the per-lane dashed category line (P8).
  - Left rail (x 0–128): `SURFACE` fill, 1px `BORDER_SOFT` right edge. Inside: category dot (8px) + UPPERCASE 10px label (`TEXT_DIM`) + right-aligned count chip (10px `TEXT_MUTED` on `SURFACE_ALT`, radius 8).
  - Active lane (holds the selected event category): label brightens to `TEXT`, dot full opacity; inactive lane dots at 70%. Calm focus cue, no motion.
- Time grid: faint vertical lines in `BORDER_SOFT` dotted at a time-meaningful interval with small timestamp ticks on a top ruler, so empty gaps read as "quiet time", not "broken layout".

### 5.2 Event card styling (`EventCardItem.paint`) — per state (body always `CARD_BG`, accent = category)

| State | Stripe | Border | Body | Title | Extra |
|-------|--------|--------|------|-------|-------|
| Default | 4px category | 1px BORDER | CARD_BG | 13/600 TEXT | dot 8px; subtitle 11 TEXT_MUTED; meta line 10 TEXT_DIM (`231ms`, ts) |
| Hover | 4px category | 1px category @60% | CARD_BG_HOVER | TEXT | cursor pointer; 1px top inner highlight |
| Selected | 4px category | 1.5px category | CARD_BG_HOVER | TEXT | ELEV_SEL_RING 1.5px **solid** ring at -6px, radius+3 |
| Error / level=ERROR | 4px STATE_ERROR | 1.25px STATE_ERROR | CARD_BG + 6% red wash | TEXT | flat warn triangle top-right (not filled `!` bubble), red dot |
| Warning level | 4px category | 1px STATE_WARN @50% | CARD_BG | TEXT | thin amber underline under title |
| New (arrived) | as default | category @100% 600ms then settle | — | — | Motion §10 arrival |
| Muted (filtered ghost) | 4px @25% | 1px BORDER_SOFT | CARD_BG @50% | TEXT_DIM | non-interactive |

Internal layout (176x58): 4px stripe -> 12px pad -> 8px dot -> title (13/600) -> subtitle (11) -> meta (10 mono `200 . 231ms`). Change selection from dashed to **solid** ring (dashed hard to find at zoom-out, P7). Add explicit hover (none today).

### 5.3 Dense-event treatment (the P1 fix — collection cards)
When events fall in the same lane inside a collision window (overlap in x at current zoom), **do not stack**. Collapse into one **collection card**:
- Visual: stacked-paper motif — 2 offset ghost rects behind the front card (offset 3px / 6px, each progressively darker CARD_BG -> SURFACE_DARK, 1px BORDER_SOFT). Front card shows the most-significant event (error > warning > newest).
- Count badge: pill top-right, SURFACE_ALT bg, 10/600 TEXT, e.g. `+12`.
- Category chips: 4–6px row of category-colored dots along the bottom edge for the mix inside (max 5 then `...`). One glance: "12 events, mostly TOOL + 1 ERROR".
- Error precedence: any error in the group -> collection border + a small red dot in the chip row, so errors never hide inside a collapse.
- Interaction: click/zoom-in **fans** children out along the lane (spring ~180–220ms; reduced-motion instant) into individual cards; collapse reverses.
- Compute in a new `_collapse_dense()` pass over `_layout_events` output (group by lane + x-bucket), keeping `populate_events` O(n).

### 5.4 Connectors (`ConnectorItem`) — discipline for density (P6)
- Keep below cards (`setZValue(-5)`) but reduce weight: 1px, color = end category at **35% alpha** for inferred (dashed) links, **55%** for explicit parent/child (solid).
- Only render the **selected event** run/request chain at full strength; all other connectors drop to 12% alpha or hide above a density threshold. Spider-web becomes "click a card -> see its thread".
- Curve: cubic bezier, clamp control-point horizontal offset so near-vertical links do not loop. Round caps.

### 5.5 Acceptance criteria (timeline)
- At 264 events no two cards visually overlap; bursts render as collection cards; idle gaps compressed/marked, not empty voids.
- Any error in a collapsed group is visible without expanding.
- Selecting a card highlights only its thread connectors.
- Category identifiable by stripe+dot color at 100% zoom without reading text.

---

## 6. Inspector visual system (P3)

Target = `assets/mockups/bridge_tracer/event_detail_inspector.png`.

- **Header:** eyebrow `EVENT INSPECTOR` (10/600 TEXT_DIM UPPERCASE) -> event title (18/600 TEXT) -> small pills: category pill (category color text on SURFACE_ALT, radius pill) + level pill.
- **Key/value rows:** two-column. Key column fixed ~96px, 10/600 UPPERCASE TEXT_DIM, right-aligned to gutter; value 12/400 TEXT, mono for ids/durations/tokens. Row 24px, 8px gap — biggest readability win. Group rows inside an `inspector_section` card (`#0b1526`, 1px `#1f2a3d`, radius 10), lg(16) padding.
- **Section spacing:** xl(24) between sections; each gets a 10/600 eyebrow (`RAW RESPONSE PREVIEW`, `RELATED EVENTS`, `RAW JSON VIEWER`).
- **Raw JSON box:** real height (min 160px), mono 11, SURFACE_DARK well, optional low-saturation syntax tint (keys TEXT_MUTED, strings `#9ece9e`, numbers `#d6a76a`).
- **Related events:** chips ("parent: HTTP POST /api/send") with category-colored left dot, SURFACE_ALT bg, clickable, hover -> CARD_BG_HOVER. Click selects + scrolls timeline.
- **Actions** (Copy JSON / Pin / Compare): bottom, ghost buttons, ACCENT border on hover.
- Raise inspector `min` so rows are not cramped (coordinate exact px with product designer; ~360px seats two-column rows).

---

## 7. Filter / sidebar visual system

Target = `assets/mockups/bridge_tracer/filter_recording_sidebar.png`.

- **Section eyebrows:** `CONNECTION`, `RECORDING`, `PRE-RECORD FILTERS` — 10/600 UPPERCASE TEXT_DIM, lg top margin.
- **Setting rows:** label left (12 TEXT), value/state right (12 TEXT_MUTED, or `valid`/`ready`/`idle`). Row = SURFACE_ALT card, radius 8, 10px pad, 6px gap. State word uses state color (`valid` -> STATE_LIVE_DIM, `disabled` -> TEXT_FAINT).
- **Toggle pills:** Off = track SURFACE_DARK, knob TEXT_DIM. On = track STATE_LIVE @~90%, knob white, slides right. Build as `QPushButton[checkable]` styled by QSS `:checked`, or a custom widget with a 140ms knob `QPropertyAnimation`. Active filter rows get a 2px ACCENT left edge (fixes "filters need clearer active/inactive states").
- **Filter chips (HTTP/LLM/Tool/Errors-only/Search):** segmented pills along the timeline top. Inactive = SURFACE_ALT/TEXT_MUTED; active = category-tinted bg @18% + category text + 1px category border. Search chip shows the live query (`Search: max_tokens`).
- **Trigger cards** (`trigger_card`, 80px fixed): keep height, add category dot + title + mono sub (`/api/send`, `read_file/write_file`); toggle pill right.

---

## 8. Splitter / resize affordance (P5)

- Handle width 8px (from 6). Default BORDER_SOFT; hover = 2px center grip line in ACCENT + 3 faint 1px grip dots (paint in a `QSplitterHandle` subclass). Active/drag: full ACCENT.
- Cursor: SplitHCursor/SplitVCursor on hover (Qt provides this with nonzero handle size).
```css
QSplitter::handle { background: #1a2740; }
QSplitter::handle:hover { background: #233553; }
QSplitter::handle:horizontal { width: 8px; }
QSplitter::handle:vertical { height: 8px; }
```
- First-run hint: one-time 1200ms-decaying ACCENT tint on handles after first data load (reduced-motion -> static tint for 3s).

---

## 9. Live / recording / error / empty / loading / disconnected states

The affordance system (fixes P2 and P9). Centralize as a **status pill** + per-state canvas/banner treatment.

### 9.1 Status pill (replace plain `status_label`)
Rounded pill, top-right, SURFACE_ALT bg, 1px BORDER: state dot + state text + `. {count} events`.

| State | Dot | Text | Dot motion |
|-------|-----|------|-----------|
| Connected/idle | STATE_IDLE solid | `ready . connected` | none |
| **Recording (LIVE)** | STATE_LIVE | `REC . live . 264 events` | breathing pulse 1400ms (opacity 0.55<->1.0) |
| Reconnecting | STATE_WARN | `reconnecting...` | gentle blink 900ms |
| Error | STATE_ERROR | `error . {short}` | static + one 200ms pill shake |
| Disconnected | STATE_ERROR @70% | `disconnected` | static |

The breathing REC dot is the persistent "we are live" signal the build lacks. A matching 2px STATE_LIVE top hairline across the timeline header during recording reinforces it without coloring the whole UI.

### 9.2 Event arrival (live)
New cards animate in (§10). A non-flashing "+1" count tick in the pill (digit rolls up) confirms ingestion even if the new card is off-screen / inside a collapsed group.

### 9.3 Reconnect / error (relates to SSE-timeout bug, Workstream H)
- Reconnecting: thin STATE_WARN progress hairline under the header (indeterminate, 1200ms loop), pill -> WARN. Calm, not alarming.
- Hard error / disconnect: slim dismissible banner under the toolbar, STATE_ERROR @12% bg, 1px STATE_ERROR, icon + message + `Retry` ghost button. Never full-screen red. Keep already-rendered cards on disconnect.

### 9.4 Empty / first-run
Centered, friendly: soft monochrome line-icon, `Connect to a bridge to begin tracing`, primary `Connect` button (ACCENT), subtext `Live events will appear here as they arrive.` on BACKGROUND with a faint lane scaffold ghosted at 6%. Satisfies "useful before configuration".

### 9.5 Loading / first snapshot
While the SSE `snapshot` is inbound: 3–5 skeleton cards per active lane (rounded rects, SURFACE_ALT, slow 1200ms shimmer). Replaced by real cards on arrival (cross-fade 160ms). Reduced-motion = static skeletons.

---

## 10. Motion system

Global: 120–220ms microinteractions; <=320ms only for multi-element transitions (fan-out, panel resize). Easing: enter `OutCubic`; reflow/fan-out `OutQuint`; exit `InCubic`; color cross-fade `InOutSine`. Batched arrivals stagger 18ms/card, cap added latency ~120ms (never delay reading).

| Interaction | Property | Duration | Easing | Reduced-motion |
|-------------|----------|----------|--------|----------------|
| New event arrival | opacity 0->1 + y -6px->0 | 180ms | OutCubic | instant opacity 1, no move |
| Selection change | ring opacity 0->1 + grow | 140ms | OutCubic | instant ring |
| Card hover | body CARD_BG->CARD_BG_HOVER | 120ms | InOutSine | instant |
| Collection fan-out / collapse | child x/y | 200ms (±220) | OutQuint | instant snap |
| Filter apply | opacity + slight x | 160ms | OutCubic/InCubic | instant show/hide |
| Filter panel collapse | maximumHeight | 180ms (already) | OutCubic | instant |
| REC dot breathing | opacity 0.55<->1.0 | 1400ms loop | InOutSine | static at 1.0 |
| Reconnecting hairline | x sweep | 1200ms loop | linear | static 30% bar |
| Error pill shake | x +-3px x2 | 200ms | OutSine | no shake; color swap only |
| Skeleton shimmer | gradient x | 1200ms loop | linear | static |
| Status count tick | digit roll | 140ms | OutCubic | instant swap |
| Zoom (Ctrl+wheel) | view transform | 120ms | OutCubic | instant |

All via `QPropertyAnimation`/`QVariantAnimation` on `QGraphicsObject` items (cards already are `QGraphicsObject`, so `pos`/`opacity` animate directly) — consistent with the existing `_filter_anim` pattern.

---

## 11. Microinteraction specs

- **Card click:** 60ms press (scale 0.99) -> release emits select; ring animates in (140ms).
- **Hover into card:** body lightens (120ms) + cursor pointer + tooltip (already wired).
- **Connector reveal on select:** selected thread connectors fade 12%->full (160ms); others dim to 12% (160ms).
- **Toggle pill:** knob slides (140ms OutCubic) + track cross-fades (140ms). Off->on uses STATE_LIVE.
- **Filter chip activate:** bg tint + border fade in (120ms); 1px underline grows L->R (140ms) as the active tell.
- **Copy JSON:** label cross-fades `Copy JSON`->`Copied` (120ms), reverts after 1.2s. No toast.
- **Jump to selected run / related chip click:** ensureVisible scroll 200ms ease ONLY when target off-screen (avoid forced-scroll-on-rebuild, see baseline `does_not_force_scroll_on_rebuild`); target ring pulses once (220ms).
- **Splitter drag:** handle -> ACCENT on press; live resize with no animation during drag (must feel direct).

---

## 12. Reduced-motion behavior

Single app setting `reduced_motion: bool` (follow OS where detectable; expose a toggle). ON degrades every animation to its instant/static variant:
- No arrival translate/scale (opacity set to 1, or a single <=100ms fade).
- Fan-out/collapse = instant snap.
- REC dot solid; reconnecting static 30% hairline; skeleton static; error = color/banner only, no shake.
- Count tick = direct number replace. Zoom & scroll instant.
Implement as a guard helper `animate(obj, prop, ...)` that, if reduced_motion, calls `setProperty` directly and returns — centralizes compliance, painters unchanged.

---

## 13. North-star summary (REQUESTED ITEM 1)

Finished Bridge Tracer reads like the mockups: a **calm dark control room** where (1) you always know if you are live (breathing REC pill + header hairline), (2) hundreds of events stay readable because bursts collapse into informative collection cards instead of overlapping stacks, (3) color means category/severity and nothing else, (4) the inspector is a spacious two-column readout, (5) filters/triggers are obvious toggle pills with clear active states, (6) errors and reconnects are noticeable but never panic-inducing, and (7) subtle 120–220ms motion explains every state change and disappears. Useful on first launch (friendly empty + connect), fast to scan, hard to misuse, fully buildable in PySide6/Qt.

---

## 14. Pain-point remedies — 2–3 ranked ideas each (REQUESTED ITEM 4)

Ranking key: **Impact / Effort** (H/M/L). Top idea in each is the recommended pick.

### P1 — Stacked / unreadable timeline at volume
1. **Collection cards with fan-out (RECOMMENDED).** Collapse same-lane x-collisions into one stacked-paper card: count badge + category chip row + error precedence; click/zoom fans children out (200ms OutQuint, reduced-motion instant). *Impact H / Effort M.* Kills the 264-event stack; errors never hide.
2. **Index/log-based X (eliminate dead gaps).** Position by sequence-within-window instead of raw wall-clock at high density, with time ticks on the ruler. *Impact H / Effort M.* Pairs with #1 as the layout under collapsed groups.
3. **Lane packing / collision avoidance.** Keep timestamp X but nudge overlaps into sub-rows within a lane. *Impact M / Effort L.* Cheapest stopgap; removes literal overlap.

### P2 — Weak live / recording affordance
1. **Breathing REC status pill + header hairline (RECOMMENDED).** Green pulsing dot (1400ms) + `REC . live . N events` + 2px STATE_LIVE header line during recording. *Impact H / Effort L.*
2. **Live count tick + arrival motion.** Digit roll on ingest + card arrival fade/slide so activity is felt off-screen. *Impact M / Effort L.*
3. **Ambient live canvas cue.** Faint top-edge gradient or a 1px ruler tick that advances while recording. *Impact M / Effort M.* Keep extremely subtle (no neon).

### P3 — Cramped inspector
1. **Two-column key/value with section cards (RECOMMENDED).** 96px UPPERCASE key gutter, mono values, 24px rows, 24px section gaps, taller JSON well. *Impact H / Effort L-M.* Matches mockup.
2. **Raise inspector min width + larger raw-JSON box (>=160px).** *Impact M / Effort L.* (Coordinate px with product designer.)
3. **Related-events chips + Pin/Compare actions.** Category-dot clickable chips, ghost buttons. *Impact M / Effort M.*

### P4 — Tiny logs strip
1. **Resizable splitter pane, min ~120px (RECOMMENDED).** Mono rows, level-colored left dot (LEVEL_COLORS), timestamp gutter. *Impact M / Effort L.*
2. **Collapsible logs drawer.** Header bar with count + chevron (180ms height anim). *Impact M / Effort M.*
3. **Inline severity filter on logs.** DEBUG/INFO/WARN/ERROR chips reusing the filter-chip treatment. *Impact L / Effort M.*

### P5 — Faint splitter handles
1. **8px handle + hover grip (center line + dots) in ACCENT (RECOMMENDED).** *Impact M / Effort L.*
2. **One-time first-run handle tint hint** (reduced-motion = 3s static tint). *Impact M / Effort L.*
3. **Persistent faint grip dots at rest** so affordance never depends on hover. *Impact L / Effort L.*

### P6 — Connector spider-web
1. **Thread-on-select focus (RECOMMENDED).** Only the selected event chain at full strength; rest 12% or hidden. *Impact H / Effort M.*
2. **Alpha + weight discipline.** 1px, 35% inferred / 55% explicit, below cards. *Impact M / Effort L.* (Do regardless.)
3. **Density cutoff.** Above ~150 visible events hide inferred connectors until a card is selected. *Impact M / Effort L.*

### P7 — Flat card hierarchy
1. **Solid selection ring + explicit hover + meta line (RECOMMENDED).** Per §5.2; mono meta (`200 . 231ms`). *Impact M / Effort L.*
2. **Severity body wash** (6% red / amber underline) so severity reads pre-attentively. *Impact M / Effort L.*
3. **Title weight bump to 13/600** so titles win over connectors. *Impact M / Effort L.*

### P8 — Low-contrast / stripey lanes
1. **Quiet rail, remove colored centerlines (RECOMMENDED).** Flat lanes, boundary hairlines, clean left rail (dot+label+count chip), active-lane brightening. *Impact M / Effort M.*
2. **Active-lane emphasis only** (dim inactive lane labels/dots to 70%). *Impact L / Effort L.*
3. **Top time ruler with ticks** so empty gaps read as quiet time. *Impact M / Effort M.*

### P9 — No empty/loading/disconnected language
1. **Friendly empty + Connect CTA with ghosted lane scaffold (RECOMMENDED).** *Impact H / Effort L-M.*
2. **Skeleton cards during first snapshot** (shimmer; reduced-motion static). *Impact M / Effort M.*
3. **Dismissible disconnect/error banner with Retry; keep existing cards.** *Impact M / Effort M.* (Pairs with Workstream H.)

### P10 — Token/category drift & collisions
1. **Fix AUTH/PARSER collision + promote hard-coded hexes to tokens (RECOMMENDED).** PARSER -> `#c084fc`; add CARD_BG, ELEV_SEL_RING, STATE_* to `theme.py`. *Impact M / Effort L.*
2. **Single source of truth for state colors** (STATE_LIVE/WARN/ERROR) across pill, banners, card severity. *Impact M / Effort L.*
3. **Contrast audit pass** of category colors at 8px on CARD_BG. *Impact L / Effort L.*

---

## 15. Implementation notes (where each change lands)

- `src/ui/theme.py`: add tokens (CARD_BG, CARD_BG_HOVER, BORDER_SOFT, ELEV_SEL_RING, STATE_*, ACCENT, TEXT_FAINT); fix PARSER color; align ERROR to STATE_ERROR.
- `src/ui/timeline_view.py`:
  - `EventCardItem.paint` -> use tokens (drop hard-coded `#0d1728`, `#ef4444`, `#d9e4ff`); add hover, solid selection ring, meta line, severity wash, flat warn glyph.
  - new `_collapse_dense()` after `_layout_events`; new `CollectionCardItem(QGraphicsObject)` for stacked-paper + badge + chips + fan-out (`QPropertyAnimation` on child `pos`).
  - `ConnectorItem.paint` / `_create_connectors` -> alpha/weight discipline + selected-thread focus.
  - `TimelineScene.drawBackground` -> quiet rail, remove colored centerlines, add top time ruler, active-lane emphasis.
- `src/ui/main_window.py`:
  - replace `status_label` text with a status-pill widget (dot + text) + recording header hairline; add reconnect hairline + disconnect banner; add empty-state + skeleton widgets.
  - `_STYLE`: add toggle-pill `:checked` QSS, filter-chip active styles, inspector two-column row styles, splitter 8px + grip, logs pane styling; raise logs from fixed 42px to a splitter pane (min ~120).
  - central `animate(obj, prop, dur, easing)` helper honoring `reduced_motion` (reuse existing `QPropertyAnimation`/`QEasingCurve` import).
- Validate every change against `docs/diagnostic-shots/live_recording.png` density, not the 8-event sample.

### Global acceptance criteria
- 264-event live render: zero overlapping cards; errors visible without expanding; one obvious LIVE indicator.
- Category identifiable by color at 100% zoom; AUTH != PARSER.
- Inspector two-column rows legible; JSON box >= 160px.
- Splitters discoverable; logs readable.
- Every animation has a reduced-motion path; nothing animates longer than 220ms in the interaction path (loops excepted).
