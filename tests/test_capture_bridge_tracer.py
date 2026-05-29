from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from scripts.capture_bridge_tracer import capture_config_screenshots


def _app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def test_capture_script_writes_every_configured_visual_state(tmp_path: Path) -> None:
    _app()
    config = [
        {
            "op": "visual_diff",
            "id": "bridge_tracer.main_desktop_timeline",
            "name": "Main Desktop Timeline",
            "test": {"img": str(tmp_path / "main.png"), "viewport": [0, 0, 1440, 900]},
            "ref": {"img": "assets/mockups/bridge_tracer/main_desktop_timeline.png", "viewport": [0, 0, 1440, 900]},
            "out": {"diff": str(tmp_path / "main.diff.png")},
            "threshold": {"mean": 8.0, "max_changed_ratio": 0.12},
        },
        {
            "op": "visual_diff",
            "id": "Bridge_Tracer.event_detail_inspector",
            "name": "Event Detail Inspector",
            "test": {"img": str(tmp_path / "detail.png"), "viewport": [0, 0, 1440, 900]},
            "ref": {"img": "assets/mockups/bridge_tracer/event_detail_inspector.png", "viewport": [0, 0, 1440, 900]},
            "out": {"diff": str(tmp_path / "detail.diff.png")},
            "threshold": {"mean": 8.0, "max_changed_ratio": 0.12},
        },
    ]
    config_path = tmp_path / "visual_config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    written = capture_config_screenshots(config_path=config_path, project_root=Path.cwd())

    assert {path.name for path in written} == {"main.png", "detail.png"}
    assert all(path.exists() and path.stat().st_size > 0 for path in written)
