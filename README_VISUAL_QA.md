# Visual QA for Bridge_Tracer

Mandatory agent inputs:

- `visual_acceptance_spec.json`
- `visual_diff_config.json`
- `visual_diff_config.schema.json`
- `visual_diff_config.example.json`
- `assets/mockups/`

Run from workspace root:

```bash
python scripts/visual_qa/visual_diff.py --config ../Bridge_Tracer/visual_diff_config.json
```

Import mockups:

```bash
python scripts/visual_qa/import_mockups.py --project ../Bridge_Tracer --zip path/to/assets.zip --mockup-set Bridge_Tracer
```

Codex is responsible for creating project-local screenshot capture scripts and appending visual diff entries to `visual_diff_config.json`.

