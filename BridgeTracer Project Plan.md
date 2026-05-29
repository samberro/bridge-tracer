# Project Plan: BridgeTracer

## Goal

Build a windowed desktop trace tool for visually inspecting what happens inside the AI bridge.

The tool should record bridge events such as endpoint hits, config changes, LLM requests, LLM responses, tool calls, tool results, file references, errors, and internal state transitions. It should display them in a timeline/filmstrip/train-track style UI so debugging bridge behavior is fast and visual.

The UI should support:

* pre-record filtering
* post-record filtering
* recording triggers
* stop triggers
* visual timeline inspection
* event detail inspection
* saved recordings
* file reference retrieval after recording

## Core Requirements

### 1. Event Recording

Create an event recording system that can capture all or selected bridge events.

Events should include, but are not limited to:

* bridge startup/shutdown
* config loaded/changed
* endpoint hit
* request received
* response returned
* message sent to LLM
* raw LLM response
* parsed assistant response
* tool call detected
* tool execution started
* tool execution finished
* tool execution failed
* file reference created
* file reference retrieved
* MCP call started/finished
* auth success/failure
* errors/exceptions
* warnings
* timing/performance metrics

Each event should have a normalized schema.

Suggested event shape:

```json
{
  "id": "evt_uuid",
  "run_id": "run_uuid",
  "session_id": "session_uuid",
  "request_id": "request_uuid",
  "timestamp": "2026-05-28T12:34:56.789Z",
  "type": "llm.request",
  "category": "llm",
  "level": "info",
  "summary": "Sent chat completion request to LM Studio",
  "details": {},
  "refs": [],
  "duration_ms": null,
  "parent_event_id": null
}
```

Event categories should be consistent and colorable:

```text
system
config
http
auth
session
llm
tool
mcp
file
parser
error
performance
```

### 2. Recording Session Control

Implement a recording session model.

Recording lifecycle states:

* idle
* recording
* stopping
* stopped
* failed

Required behavior:

* visible Start Recording button
* visible Stop Recording button
* stop button ends the active recording session cleanly
* stop closes stream subscriptions or polling loops
* stop flushes buffered events
* stop marks recording end time
* stop triggers post-record tasks, including file ref retrieval
* stop should not lose events already received
* stop should be testable outside the UI

### 3. Pre-Record Filters

Before recording starts, allow the user to choose which events to subscribe to.

Examples:

* record everything
* record only one session
* record only one request/run
* record only LLM traffic
* record only tool calls/results
* record only errors
* record only file refs
* record only MCP events
* record selected endpoint names
* record selected event categories

Pre-record filters should reduce noise and avoid storing unnecessary data.

The filter layer should exist outside the UI so it can be unit tested.

### 4. Recording Triggers

Support recording triggers so recording can start automatically when interesting events happen.

Start triggers:

* manual start
* start when selected endpoint is hit
* start when selected session ID appears
* start when selected request ID appears
* start when selected run ID appears
* start when selected event type appears
* start when warning/error event appears
* start when selected tool is called
* start when request is sent to selected model
* start when file ref is created

Stop triggers:

* manual stop
* stop after N events
* stop after timeout
* stop after selected response event appears
* stop after request/run completes
* stop on error
* stop when selected event type appears

Triggers should be part of business logic, not UI-only logic.

### 5. Post-Record Filters

After events are recorded, allow the UI to filter what is visible without modifying the saved recording.

Post-record filters:

* category toggles
* event type search
* text search
* show/hide details
* show only errors
* show only selected request/run/session
* show events with file refs
* show events with tool calls
* min/max duration
* time range
* collapse/expand groups

Post-record filters should be fast and reversible.

### 6. Visual Timeline

Create a windowed UI that renders events as a visual timeline.

Preferred layout:

* top toolbar with Connect, Start Recording, Stop Recording, Save, Load
* left side: filters and run/session selector
* center: timeline/filmstrip/train-track view
* right side: selected event inspector
* bottom or collapsible panel: raw JSON/details/log output

Timeline behavior:

* events appear as compact cards or nodes
* events are summarized by default
* clicking an event opens full details
* related events are visually connected
* parent/child events can be grouped
* request/run/session can have separate lanes
* tool calls can appear as child tracks under an LLM event
* errors should be visually obvious
* long-running events should show duration
* current selected event should be highlighted

Example visualization concept:

```text
HTTP ──● request.received ──● response.sent
LLM  ───────● llm.request ─────────● llm.response
Tool ─────────────● read_file ─────● result
File ─────────────────────● file_ref.retrieved
```

### 7. Event Summaries

Events should be summarized until clicked.

Summary examples:

```text
HTTP POST /api/send → 200 in 231ms
LLM request sent: 12 messages, 4,201 tokens
Tool call: read_file(config.py)
Tool result: 18,204 chars returned
Error: JSON parse failed
File ref retrieved: screenshot.png, 412 KB
```

Clicking an event should show:

* full event JSON
* request/response body if available
* timing information
* related event IDs
* file refs
* parsed tool call/result
* raw payload
* error stack trace if present

Large payloads should be truncated in the timeline but available in the detail panel.

### 8. Color Coding

Color code events by category and severity.

Suggested mapping:

```text
system       gray
config       blue-gray
http         blue
auth         purple
session      teal
llm          indigo
tool         orange
mcp          pink
file         green
parser       yellow
error        red
performance  cyan
```

Severity:

```text
debug/info   normal
warning      yellow border
error        red border/background accent
success      green accent
```

The color system should live in a UI constants/theme file.

### 9. File Reference Retrieval

If events include `file_refs`, retrieve the referenced file data after recording.

Rules:

* retrieval happens post-recording
* limit max file size
* limit total retrieval size
* retrieve metadata always
* inline text files up to a configured char limit
* images should be available for preview
* binary files should show metadata only unless supported
* failed retrieval should create a `file.ref.retrieve_failed` event

Suggested limits:

```text
max_file_bytes_per_ref = 5 MB
max_total_file_bytes = 50 MB
max_inline_text_chars = 100,000
```

File ref detail shape:

```json
{
  "ref_id": "file_abc",
  "path": "tmp_workspace/output.txt",
  "mime": "text/plain",
  "size_bytes": 12345,
  "retrieved": true,
  "truncated": false,
  "content_preview": "..."
}
```

### 10. Bearer Token Auth

The Tracer should connect to the bridge using Bearer token auth.

Requirements:

* token input field
* save last token locally
* allow clearing saved token
* use token for bridge API calls
* handle 401/403 clearly
* never log token in event payloads
* redact token if it appears in headers/logs

Suggested storage:

* local app config file for dev
* OS keychain later if easy
* saved token should be optional

Auth header:

```http
Authorization: Bearer <token>
```

### 11. Separate Business Logic From UI

The UI should not contain recording/filtering/storage logic directly.

Suggested architecture:

```text
src/
  app/
    main.py
  core/
    events.py
    recorder.py
    filters.py
    triggers.py
    storage.py
    file_refs.py
    auth.py
    schemas.py
  bridge_client/
    client.py
    stream.py
  ui/
    app_window.py
    timeline_view.py
    event_card.py
    event_detail.py
    filters_panel.py
    recording_controls.py
    theme.py
  tests/
    test_events.py
    test_filters.py
    test_triggers.py
    test_recorder.py
    test_file_refs.py
    test_auth_redaction.py
```

Core modules should be UI-independent and testable.

Business logic responsibilities:

* event schema validation
* event normalization
* event filtering
* recording triggers
* stop triggers
* recording state
* event storage/load
* file ref retrieval
* auth header handling
* token redaction
* bridge API client

UI responsibilities:

* display events
* user interaction
* filter controls
* trigger controls
* timeline rendering
* event detail panels
* token input
* start/stop recording controls

### 12. Unit Tests and Coverage

Implement unit tests with at least 90% coverage for business logic.

Required tests:

* event schema creation
* event normalization
* event ordering
* recording lifecycle
* start recording behavior
* stop recording behavior
* stream cleanup on stop
* buffered event flushing on stop
* pre-record filters
* post-record filters
* recording triggers
* stop triggers
* category filters
* text search filters
* duration filters
* token redaction
* bearer token header creation
* file ref retrieval limits
* file ref truncation
* storage save/load round trip
* malformed event handling
* missing fields handling
* timeline grouping logic
* parent/child event relationship logic

UI tests are nice but not required for 90% if difficult. Focus coverage on `core/` and `bridge_client/`.

## Suggested Tech Stack

Use Python.

Preferred UI option:

```text
PySide6 / Qt
```

Reason:

* real desktop window
* good timeline rendering
* good split panels
* good model/view support
* easier than browser packaging
* works well with Python business logic

Alternative:

```text
Textual
```

Only use Textual if we want terminal UI. For this project, prefer PySide6 because the goal is a visual windowed timeline.

Suggested dependencies:

```text
pydantic
httpx
PySide6
pytest
pytest-cov
python-dateutil
```

Optional:

```text
orjson
rich
watchdog
keyring
```

## Recording Modes

Support at least two recording modes.

### Pull Mode

The Tracer periodically fetches events from the bridge:

```text
GET /trace/events?since=<cursor>
```

Good fallback.

### Stream Mode

The Tracer subscribes to a bridge event stream:

```text
GET /trace/events/stream
```

This can use SSE or WebSocket.

Prefer SSE first because it is simpler.

## Bridge API Assumptions

The bridge should expose trace endpoints.

Suggested endpoints:

```http
GET  /trace/events
GET  /trace/events/stream
GET  /trace/file_refs/{ref_id}
GET  /trace/runs
GET  /trace/sessions
```

All require Bearer auth.

If these endpoints do not exist yet, create the Tracer with a mock provider first, then wire the real bridge client.

## MVP Scope

MVP should include:

- PySide6 desktop window
- token input/save
- connect/disconnect
- start/stop recording
- visible Stop Recording button
- recording lifecycle state
- event stream client
- normalized event model
- event list/timeline
- color-coded event cards
- selected event details panel
- pre-record category filters
- post-record category filters
- saved filter presets
- basic recording triggers
- basic stop triggers
- search box
- waterfall-style latency lanes
- screenshot/image preview
- diff viewer for file changes
- compare two events from same or different recordings
- file ref metadata retrieval
- JSON save/load recording
- export JSONL
- unit tests for core logic
- 90%+ coverage for core modules

## Non-MVP / Later

Later features:

- timeline zoom
- replay mode
- export HTML report
- auto-detect noisy event types
- bookmarks
- comments/annotations
- keyboard shortcuts
- multiple bridge connections
- OS keychain token storage



## Implementation Phases


### Phase 1: Core Event Model and Recording Session Control

* define event schema
* define event categories
* define event severity levels
* implement event normalization
* implement event sorting
* implement sample/mock events
* implement recording session model
* implement recording lifecycle states:

  * idle
  * recording
  * stopping
  * stopped
  * failed
* implement explicit Stop Recording action
* stop button should end the active recording session cleanly
* stop should close stream subscriptions or polling loops
* stop should flush buffered events
* stop should mark recording end time
* stop should trigger post-record tasks, including file ref retrieval
* unit tests

### Phase 2: Filters and Recording Triggers

* implement pre-record filter model
* implement post-record filter model
* implement category/type/text/duration filters
* implement filter presets
* implement recording triggers
* support manual trigger:

  * user clicks Start Recording
* support endpoint trigger:

  * start recording when selected endpoint is hit
* support session trigger:

  * start recording when selected session ID appears
* support request/run trigger:

  * start recording when selected request ID or run ID appears
* support event-type trigger:

  * start recording when selected event type appears
* support error trigger:

  * start recording when warning/error event appears
* support tool trigger:

  * start recording when selected tool is called
* support LLM trigger:

  * start recording when request is sent to selected model
* support stop triggers:

  * stop after N events
  * stop after timeout
  * stop after matching response event
  * stop after request/run completes
  * stop on error
* unit tests

### Phase 3: Storage

* save recording to JSON or JSONL
* load recording
* validate loaded events
* preserve recording metadata:

  * start time
  * stop time
  * duration
  * active filters
  * active triggers
  * event count
* unit tests

### Phase 4: Bridge Client

* Bearer auth client
* SSE event stream
* fallback polling mode
* error handling
* token redaction
* reconnect handling
* clean disconnect on stop
* unit tests with mocked HTTP

### Phase 5: UI Skeleton

* PySide6 app window
* top toolbar
* left filters panel
* recording controls
* center timeline/list
* right details panel
* bottom raw JSON panel
* mock event provider

### Phase 6: Timeline Rendering

* event cards
* color coding
* grouping by run/session/request
* selected event highlighting
* parent/child visualization
* duration display
* lane rendering
* compact summaries
* click-to-inspect behavior

### Phase 7: File Ref Retrieval

* retrieve refs after recording
* enforce limits
* inline text previews
* image metadata
* attach retrieved refs to recording
* generate retrieval failure events
* unit tests

### Phase 8: Integration

* connect UI to bridge client
* live recording
* start/stop controls
* trigger controls
* save/load recordings
* polish errors and empty states

### Phase 9: Coverage and Hardening

* reach 90%+ coverage
* add malformed-event tests
* add auth failure tests
* add stream disconnect/reconnect tests
* add large payload tests
* add redaction tests
* add stop cleanup tests
* add trigger behavior tests

## Acceptance Criteria

The project is done when:

* app opens as a desktop window
* user can enter/save Bearer token
* user can connect to bridge
* user can start recording
* user can stop an active recording session with a visible Stop button
* stopping recording flushes events and closes live subscriptions cleanly
* user can configure recording triggers before recording starts
* selected event categories can be subscribed before recording
* recorded events appear live in a timeline
* events are summarized until clicked
* clicked event shows full details
* post-record filters can hide/show noisy event categories
* events are color-coded by category/severity
* file refs are retrieved after recording within configured limits
* recordings can be saved and loaded
* business logic is separated from UI
* unit tests pass
* core/business logic has 90%+ coverage
* PySide6 UI implementation follows the approved final form/layout
- user can view waterfall-style latency lanes
- user can preview screenshots/images from retrieved file refs
- user can view file diffs when file-change data is available
- user can compare two events from same or different recordings
- user can export recordings as JSONL
- user can save and reuse filter presets

## Important Design Notes

Do not build this as one giant file.

Keep UI dumb and core logic testable.

Do not let the UI decide event semantics.

Do not log bearer tokens.

Do not retrieve unlimited file refs.

Do not block the UI thread during recording or file retrieval.

Use mock events early so UI can be designed before the bridge endpoints are final.

Prefer a functional MVP over a perfect visualization.

### Critical instruction: TDD / Test-Driven Design

For each feature, before implementation:

1. Reiterate the feature
   - restate the feature description
   - explain its function
   - explain its goal
   - define what “done” means for this feature

2. Create tests before implementation
   - identify happy-path/main-path test cases
   - identify edge cases
   - identify failure scenarios
   - define expected recovery behavior
   - write the tests first
   - confirm the tests fail before implementation when practical

3. Plan the implementation
   - describe the implementation approach
   - identify affected modules
   - identify data models/interfaces involved
   - identify integration points
   - identify safety/security concerns

4. Break the plan into discrete actionable tasks
   - each task should be small
   - each task should be verifiable
   - each task should map to one or more tests

5. Execute the tasks
   - implement only what is needed to pass the tests
   - run tests frequently
   - add more tests when new edge cases appear
   - add both main-path and edge-case tests as needed
   - refactor only after tests pass
   - keep business logic testable outside the UI

This applies to every feature, including:
- event models
- recording lifecycle
- start/stop behavior
- filters
- triggers
- storage
- JSONL export
- auth/token redaction
- file ref retrieval
- bridge client
- UI-facing view models
- timeline grouping
- event comparison
- diff handling
- screenshot/image preview metadata
- saved presets

Do not implement a feature first and add tests afterward. Tests come first.
