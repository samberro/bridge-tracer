<!-- BEGIN VISUAL_QA_TDD_RULES -->
# Codex Directive: TDD + Pixel-Perfect UI Implementation

You are implementing this project autonomously.

Do not ask the user questions.
Do not stop after partial implementation.
Do not stop when the app merely runs.
Do not stop when the feature is only functionally correct.

Your goal is:

1. Correct behavior.
2. Passing tests.
3. Visual match against approved mockups.
4. Clean, maintainable code.

---

# Core Rules

## 1. Test-Driven Development is mandatory

For every feature, before implementation:

1. Restate the feature:
   - description
   - function
   - goal
   - expected user-visible behavior
   - visual pass definition when the feature has UI

2. Write tests first:
   - happy path tests
   - main behavior tests
   - edge case tests
   - failure recovery tests
   - regression tests when fixing bugs
   - screenshot capture or deterministic visual-state tests for UI features
   - visual regression checks for existing visual_diff_config.json entries

3. Create a short implementation plan.

4. Break the plan into discrete tasks.

5. Implement only after tests exist.

6. Run tests.

7. Fix until tests pass.

8. Add more tests if new edge cases are discovered.

No feature is complete until relevant tests pass.

---

# 2. Visual implementation is mandatory for UI work

The approved mockups are the visual source of truth.

Before UI work, read:

- visual_acceptance_spec.json
- visual_diff_config.json
- visual_diff_config.schema.json
- visual_diff_config.example.json
- approved mockups under assets/mockups/

Do not reinterpret the UI.
Do not make a “rough equivalent.”
Do not simplify the layout unless technically unavoidable.

Match:

- layout
- spacing
- alignment
- panel proportions
- colors
- typography
- border radius
- shadows
- density
- button placement
- component placement
- state-specific visuals
- interaction affordances
- inspector/panel hierarchy where applicable
- raw JSON/log/debug panel placement where applicable

The app should look like a serious developer debugging/profiling/product tool.

Not a toy.
Not a demo.
Not UI oatmeal.

---

# 3. Visual QA architecture

App-specific screenshot capture is Codex responsibility.

The shared visual diff runner lives in the workspace:

```txt
scripts/visual_qa/visual_diff.py
```

The shared mockup importer lives in the workspace:

```txt
scripts/visual_qa/import_mockups.py
```

This project's cumulative visual regression config is:

```txt
visual_diff_config.json
```

This project's visual pass/test requirements are in:

```txt
visual_acceptance_spec.json
```

The config schema and example are:

```txt
visual_diff_config.schema.json
visual_diff_config.example.json
```

---

# 4. visual_diff_config.json rules

visual_diff_config.json is cumulative.

Codex must:

1. Create it if missing.
2. Append entries for new visual features.
3. Preserve old entries.
4. Never duplicate ids.
5. Never delete old ids unless the UI was intentionally removed.
6. Never weaken thresholds to pass.
7. Never replace reference mockups unless the approved mockup changed.
8. Always run the full config before declaring completion.
9. Ensure every entry conforms to visual_diff_config.schema.json.
10. Use visual_diff_config.example.json as the copyable template.

---

# 5. Required visual QA loop

After every meaningful UI change:

1. Launch the app.
2. Navigate to the relevant deterministic UI state.
3. Capture implementation screenshots.
4. Save screenshots to the paths listed in visual_diff_config.json.
5. Run visual diff against the full config.
6. Inspect generated diff images.
7. Inspect the timestamped Markdown visual QA report.
8. Fix visual mismatches.
9. Repeat until all relevant entries pass.

Run from the workspace root:

```bash
python scripts/visual_qa/visual_diff.py --config bridge_tracer/visual_diff_config.json
```

The visual diff runner prints clear PASS/FAIL output and writes timestamped Markdown reports under:

```txt
visual-checks/reports/
```

---

# 6. Visual acceptance spec rules

visual_acceptance_spec.json defines what visual pass means.

Codex must read it before UI work.

If imported mockups add feature entries, Codex must satisfy each feature's:

- visual_pass_means
- required_tests

A numeric visual diff pass is not enough by itself.
Codex must inspect screenshots and diff images for meaningful visual regressions.

A screenshot can have a low diff score and still be wrong.
A screenshot can have a high diff score due to tiny rendering differences and still be acceptable.

Use judgment.

---

# 7. Screenshot capture requirement

If a screenshot capture script does not exist for the relevant feature, create one.

It must:

- launch the app
- resize the window to a deterministic size
- navigate to the required UI state
- perform required hover/click/focus interactions when needed
- capture screenshots
- save screenshots to the paths in visual_diff_config.json
- exit cleanly

Project-local screenshot scripts usually live under:

```txt
scripts/
```

Examples:

```txt
scripts/capture_send_ui_polish.py
scripts/capture_bridge_tracer.py
```

---

# 8. Required commands

Run these before declaring completion:

```bash
python scripts/visual_qa/visual_diff.py --config bridge_tracer/visual_diff_config.json
```

Also run the project’s relevant test commands.

Examples:

```bash
pytest
python -m pytest
npm test
npm run test
npm run lint
npm run typecheck
npm run build
```

Use the commands appropriate to the repo.

---

# 9. Completion criteria

Do not stop until all are true:

- Feature was restated.
- Tests were written before implementation.
- Tests exist for the implemented feature.
- Tests pass.
- App launches.
- Screenshot capture exists or was updated for UI work.
- Screenshots are captured.
- visual_diff_config.json includes the new feature if visual.
- Old visual_diff_config.json entries are preserved.
- Visual diffs are generated.
- Timestamped Visual QA report exists.
- Full visual_diff_config.json was run.
- All relevant visual QA statuses are PASS.
- Generated diff images were inspected.
- No obvious mockup mismatch remains.
- No major UI element is missing.
- No placeholder UI remains unless explicitly intended.
- No dead/demo-only controls remain unless explicitly intended.
- Code is clean and maintainable.

---

# 10. If blocked

Do not ask the user immediately.

First:

1. Inspect the repo.
2. Search existing code.
3. Read README/docs.
4. Read visual_acceptance_spec.json.
5. Read visual_diff_config.schema.json.
6. Infer conventions.
7. Try the most likely implementation.
8. Run tests.
9. Run visual QA if relevant.
10. Fix errors.
11. Document assumptions.

Only stop if technically impossible.

If impossible, write:

```md
## Blocked

Reason:
...

What I tried:
...

Evidence:
...

Best next action:
...
```

---

# 11. Final response requirement

When done, report only:

```md
## Completed

Tests:
- ...

Visual checks:
- ...

Screenshots:
- ...

Diffs:
- ...

QA report:
- ...

Remaining deviations:
- None
```

Do not include long explanations.
Do not include implementation diary.

<!-- END VISUAL_QA_TDD_RULES -->


