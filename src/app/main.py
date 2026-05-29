from __future__ import annotations

import sys
import faulthandler

# Enable fault handler to print thread stack traces on crashes
faulthandler.enable()

from PySide6.QtWidgets import QApplication

from src.ui.interactive_window import InteractiveTracerWindow
from src.ui.sample_data import build_sample_events


def main() -> int:
    app = QApplication(sys.argv)
    window = InteractiveTracerWindow(events=build_sample_events())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
