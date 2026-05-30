from __future__ import annotations

"""Active interactive window export.

This module is intentionally kept as the entrypoint shim used by
src.app.main. It also applies narrow runtime patches for the active
MainWindow class so stale legacy modules are not involved.
"""

import os

from src.ui import main_window as _main_window


def _env_admin_token() -> str:
    token = os.environ.get("AI_BRIDGE_ADMIN_TOKEN", "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def _evaluate_current_expression_no_rebuild(self) -> None:
    """Evaluate inspector expression without recursively rebuilding UI.

    The previous implementation called _rebuild_timeline(), which calls
    _refresh_inspector(), which called _evaluate_current_expression() again
    whenever the eval box had text. That produced an immediate recursion crash
    during object/eval testing.
    """
    event = self._selected_event()
    if event is None:
        self.eval_result_box.setPlainText("unable to evaluate")
        return
    result = _main_window.evaluate_expression(self.eval_expr_edit.text(), event)
    self.eval_result_box.setPlainText(result.text if result.ok else "unable to evaluate")
    # Timeline card previews are rebuilt when rules change. Plain ad-hoc eval
    # must not rebuild the whole timeline.


# Patch the active main window module before exporting the class.
_main_window._env_auth_token = _env_admin_token
_main_window.MainWindow._evaluate_current_expression = _evaluate_current_expression_no_rebuild

InteractiveTracerWindow = _main_window.MainWindow
