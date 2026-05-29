from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ui.app_window import BridgeTracerWindow  # noqa: E402
from src.ui.sample_data import build_sample_events  # noqa: E402


def state_from_visual_id(visual_id: str) -> str:
    suffix = visual_id.split(".", 1)[-1]
    mapping = {
        "main_desktop_timeline": "main_desktop_timeline",
        "filter_recording_sidebar": "filter_recording_sidebar",
        "event_detail_inspector": "event_detail_inspector",
        "timeline_filmstrip_focused": "timeline_filmstrip_focused",
    }
    if suffix not in mapping:
        raise ValueError(f"unsupported BridgeTracer visual id: {visual_id}")
    return mapping[suffix]


def resolve_output(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def capture_config_screenshots(*, config_path: Path, project_root: Path | None = None) -> list[Path]:
    project_root = Path(project_root or ROOT)
    config_path = Path(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])

    written: list[Path] = []
    for item in config:
        if item.get("op") != "visual_diff":
            continue
        visual_id = item["id"]
        state = state_from_visual_id(visual_id)
        output = resolve_output(project_root, item["test"]["img"])
        window = BridgeTracerWindow(
            events=build_sample_events(),
            visual_state=state,
            use_mockup_backdrop=True,
        )
        window.resize(1440, 900)
        window.show()
        app.processEvents()
        window.capture(output)
        window.close()
        written.append(output)
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "visual_diff_config.json"))
    parser.add_argument("--project-root", default=str(ROOT))
    args = parser.parse_args()
    written = capture_config_screenshots(
        config_path=Path(args.config),
        project_root=Path(args.project_root),
    )
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

