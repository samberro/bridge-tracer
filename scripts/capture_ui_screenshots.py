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

def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv[:1])

    states = {
        "main_desktop_timeline": "implemented_main_desktop_timeline.png",
        "timeline_filmstrip_focused": "implemented_timeline_filmstrip.png",
        "event_detail_inspector": "implemented_event_detail_inspector.png",
        "filter_recording_sidebar": "implemented_filter_recording_sidebar.png",
    }

    output_dir = ROOT / "visual-checks" / "current"
    output_dir.mkdir(parents=True, exist_ok=True)

    for state, filename in states.items():
        window = MainWindow(events=build_sample_events(), visual_state=state)
        window.resize(1440, 900)
        window.show()
        
        # Process events to lay out and render
        for _ in range(10):
            QApplication.processEvents()
            
        out_path = output_dir / filename
        window.capture(out_path)
        print(f"Captured {state} -> {out_path}")
        window.close()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
