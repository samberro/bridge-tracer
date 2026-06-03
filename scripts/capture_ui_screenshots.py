from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ui.main_window import MainWindow
from src.ui.sample_data import build_sample_events

STATES = {
    "main_desktop_timeline": "implemented_main_desktop_timeline.png",
    "timeline_filmstrip_focused": "implemented_timeline_filmstrip.png",
    "event_detail_inspector": "implemented_event_detail_inspector.png",
    "filter_recording_sidebar": "implemented_filter_recording_sidebar.png",
}


def capture_ui_screenshots(*, output_dir: Path | None = None) -> list[Path]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv[:1])

    output_dir = Path(output_dir or ROOT / "visual-checks" / "current")
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for state, filename in STATES.items():
        window = MainWindow(events=build_sample_events(), visual_state=state)
        window.resize(1440, 900)
        window.show()

        # Process events to lay out and render
        for _ in range(10):
            app.processEvents()

        out_path = output_dir / filename
        window.grab().save(str(out_path))
        print(f"Captured {state} -> {out_path}")
        window.close()
        window.deleteLater()
        app.processEvents()
        written.append(out_path)

    return written


def main() -> int:
    capture_ui_screenshots()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
