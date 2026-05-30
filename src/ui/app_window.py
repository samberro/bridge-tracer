from __future__ import annotations

"""Compatibility shim for the old painted mockup window.

The active application entrypoint is:

    src.app.main -> src.ui.interactive_window -> src.ui.main_window.MainWindow

This module used to contain a hand-painted mockup implementation with hardcoded
bridge URL/token values. It is intentionally pruned to an alias so old imports
keep working without carrying stale UI code or unsafe defaults.
"""

from src.ui.main_window import MainWindow as BridgeTracerWindow

__all__ = ["BridgeTracerWindow"]
