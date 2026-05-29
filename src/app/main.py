from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from src.ui.app_window import BridgeTracerWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = BridgeTracerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

